from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse, get_callable
from django.db import models
from django.template.defaultfilters import striptags
from django.utils.http import base36_to_int, int_to_base36
from django.utils.translation import ugettext_lazy as _

from tcc.managers import (
    CurrentCommentManager, LimitedCurrentCommentManager,
    RemovedCommentManager, DisapprovedCommentManager,
    )
from tcc import signals
from tcc.settings import (
    STEPLEN, COMMENT_MAX_LENGTH, MODERATED, REPLY_LIMIT,
    MAX_DEPTH, MAX_REPLIES, ADMIN_CALLBACK, SUBSCRIBE_ON_POST
    )
from django.utils.safestring import mark_safe

SITE_ID = getattr(settings, 'SITE_ID', 1)

TWO_MINS = timedelta(minutes=2)


class Thread(models.Model):
    content_type = models.ForeignKey(
        ContentType, verbose_name=_('content type'),
        related_name="content_type_set_for_tcc_thread")
    object_pk = models.TextField(_('object id'))
    content_object = generic.GenericForeignKey(
        ct_field="content_type", fk_field="object_pk")
    site = models.ForeignKey(Site, default=SITE_ID,
                             related_name='tccthreads')
    is_open = models.BooleanField(_('Open'), default=True)
    is_moderated = models.BooleanField(_('Moderated'), default=MODERATED)


class Comment(models.Model):
    """ A comment table, aimed to be compatible with django.contrib.comments

    """
    # constants
    MAX_REPLIES = MAX_REPLIES
    REPLY_LIMIT = REPLY_LIMIT

    # From comments BaseCommentAbstractModel
    content_type = models.ForeignKey(
        ContentType, verbose_name=_('content type'),
        related_name="content_type_set_for_tcc_comment")
    object_pk = models.TextField(_('object id'))
    content_object = generic.GenericForeignKey(
        ct_field="content_type", fk_field="object_pk")
    site = models.ForeignKey(Site, default=SITE_ID,
                             related_name='tcccomments')
    # The actual comment fields
    parent = models.ForeignKey('self', verbose_name= _('Reply to'),
                               null=True, blank=True, related_name='parents')
    user = models.ForeignKey(User, verbose_name='Commenter')
    # These are here mainly for backwards compatibility
    ip_address = models.IPAddressField(default='127.0.0.1')
    user_name   = models.CharField(_("user's name"), max_length=50, blank=True)
    user_email  = models.EmailField(_("user's email address"), blank=True)
    user_url    = models.URLField(_("user's URL"), blank=True)
    submit_date = models.DateTimeField(_('Date'), default=datetime.utcnow)
    # Protip: Use postgres...
    comment = models.TextField(_('Comment'), max_length=COMMENT_MAX_LENGTH)
    comment_raw = models.TextField(_('Raw Comment'), max_length=COMMENT_MAX_LENGTH)
    # still accepting replies?
    is_open = models.BooleanField(_('Open'), default=True)
    is_removed = models.BooleanField(_('Removed'), default=False)
    is_approved = models.BooleanField(_('Approved'), default=not MODERATED)
    # is_public is rather pointless icw is_removed?
    # Keeping it for compatibility w/ contrib.comments
    is_public = models.BooleanField(_('Public'), default=True)
    path = models.CharField(_('Path'), unique=True, max_length=MAX_DEPTH*STEPLEN)
    limit = models.DateTimeField(
        _('Show replies from'), null=True, blank=True, db_index=True)
    # subscription (for notification)
    subscribers = models.ManyToManyField(User, related_name="thread_subscribers")
    # denormalized cache
    childcount = models.IntegerField(_('Reply count'), default=0)
    depth = models.IntegerField(_('Depth'), default=0)
    sortdate = models.DateTimeField(_('Sortdate'), db_index=True, default=datetime.now)

    unfiltered = models.Manager()
    objects = CurrentCommentManager()
    limited = LimitedCurrentCommentManager()
    removed = RemovedCommentManager()
    disapproved = DisapprovedCommentManager()

    class Meta:
        ordering = ['path']
        
    def get_parsed_comment(self, reparse=settings.DEBUG):
        if reparse:
            signals.comment_will_be_posted.send(
                sender = self.__class__, comment = self)
        parsed_comment = self.comment
        safe_comment = mark_safe(parsed_comment)
        return safe_comment

    def __unicode__(self):
        return u"%05d %s % 8s: %s" % (
            self.id, self.submit_date.isoformat(), self.user.username, self.comment[:20])

    def get_absolute_url(self):
        link = reverse('tcc_index',
                       args=(self.content_type.id, self.object_pk))
        return "%s#%s" % (link, self.get_base36())

    def clean(self):

        if self.parent:
            if not self.pk and self.parent.childcount >= self.MAX_REPLIES:
                raise ValidationError(_('Maximum number of replies reached'))
        if self.comment <> "" and striptags(self.comment).strip() == "":
            raise ValidationError(_("This field is required."))

        # Check for identical messages
        identical_msgs = Comment.objects.filter(
            user=self.user,
            comment_raw=self.comment,
            submit_date__gte=(datetime.utcnow() - TWO_MINS),
            )

        if self.id:
            identical_msgs = identical_msgs.exclude(id=self.id)

        if identical_msgs.count() > 0:
            raise ValidationError(_("You just posted the exact same content."))

    def get_root_path(self):
        if self.path:
            return self.path[0:STEPLEN]
        # The path isn't save yet: calculate it
        return self._get_path()[0:STEPLEN]

    # The following two methods may seem superfluous and/or convoluted
    # but they get the root.id of any 'node' without hitting the
    # database (again)
    def get_root_id(self):
        return base36_to_int(self.get_root_path())

    def get_root_base36(self):
        return int_to_base36(self.get_root_id())

    def get_thread(self):
        """ returns the entire 'thread' (a 'root' comment and all replies)

        a root comment is a comment without a parent
        """
        return Comment.objects.filter(path__startswith=self.get_root_path())

    def get_replies(self, levels=None, include_self=False):
        if self.parent and self.parent.depth == MAX_DEPTH - 1:
            return Comment.objects.none()
        else:
            replies = Comment.objects.filter(path__startswith=self.path)
            if levels:
                # 'z' is the highest value in base36 (as implemented in django)
                replies = replies.filter(path__lte="%s%s" % (self.path, (levels * STEPLEN * 'z')))
            if not include_self:
                replies = replies.exclude(id=self.id)
            return replies

    def get_root(self):
        if self.parent:
            return Comment.objects.get(path=self.get_root_path())
        return self

    def get_parents(self):
        if self.parent:
            parentpaths = []
            l = len(self.path)
            for i in range(0, l, STEPLEN):
                parentpaths.append(self.path[i:i+STEPLEN])
            return Comment.objects.filter(path__in=parentpaths)
        else:
            return Comment.objects.none()

    def save(self, *args, **kwargs):

        if self.id:
            is_new = False
        else:
            is_new = True

            if self.comment_raw is None or self.comment_raw == "":
                self.comment_raw = self.comment

            responses = signals.comment_will_be_posted.send(
                sender = self.__class__, comment = self)
        
            for (receiver, response) in responses:
                if response == False:
                    raise ValidationError('Comment blocked by `comment_will_be_posted` listener.')

        self.clean()

        super(Comment, self).save(*args, **kwargs)

        if is_new:

            # make sure self.limit is absolutely equal to submit_date
            self.limit = self.submit_date
            if self.parent:
                self.sortdate = self.parent.submit_date

            else:
                self.sortdate = self.submit_date

            # both _set_path and _set_limit save the model so skipping
            # it here.

            self._set_path()

            if REPLY_LIMIT and self.parent:
                self.parent._set_limit()

            # Sending this signal so *it* can be handled rather than
            # post_save which is triggered 'too soon': before
            # self.path is saved.  If there is an exception in a
            # post_save handler the path is never set and the database
            # will refuse to save another comment which is quite bad
            # for a commenting system.
            responses = signals.comment_was_posted.send(
                sender  = self.__class__, comment = self)

        else:

            # limit needs updating when a message is removed / flagged
            if REPLY_LIMIT and self.parent:
                self.parent._set_limit()

    def delete(self, *args, **kwargs):
        self.get_replies(include_self=True).delete()
        super(Comment, self).delete(*args, **kwargs)
        if self.parent:
            self.parent._set_limit()

    def _set_limit(self):
        replies = self.get_replies(levels=1).order_by('-submit_date')
        n = replies.count()
        self.childcount = n
        if n == 0:
            self.limit is None
        elif n < REPLY_LIMIT:
            self.limit = replies[n-1].submit_date
        else:
            self.limit = replies[REPLY_LIMIT-1].submit_date
        self.save()

    def get_depth(self):
        return ( len(self.path) / STEPLEN ) - 1

    def reply_allowed(self):
        return self.is_open and self.childcount < self.MAX_REPLIES \
            and ( self.depth < MAX_DEPTH - 1 )

    def can_open(self, user):
        return self.user == user

    def can_close(self, user):
        return self.user == user

    def can_approve(self, user):
        return self.user == user

    def can_disapprove(self, user):
        return self.user == user

    def can_remove(self, user):
        return self.user == user or user in self.get_enabled_users('remove')

    def can_restore(self, user):
        return self.user == user

    def get_base36(self):
        return int_to_base36(self.id)

    def _get_path(self):
        if self.parent:
            return "%s%s" % (self.parent.path, self.get_base36().zfill(STEPLEN))
        else:
            return "%s" % (self.get_base36().zfill(STEPLEN))

    def _set_path(self):
        """ This will set the path to a base36 encoding of the comment-id

        >>> 2**31
        2147483648
        >>> 2**31 / 1000 / 1000
        2147

        So 2**31 is enough for 1 million (1.000.000) comments daily for almost 6 (5.88) years

        If you really need more check out django's BigIntegerField

        >>> 2**63
        9223372036854775808L

        """
        self.path = self._get_path()
        self.depth = self.get_depth()

        self.save()

    def get_enabled_users(self, action):
        if not callable(ADMIN_CALLBACK):
            return []
        assert action in ['open', 'close', 'remove', 'restore',
                          'approve', 'disapprove']
        func = get_callable(ADMIN_CALLBACK)
        return func(self, action)
