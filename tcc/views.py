from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.conf import settings
from django.http import (HttpResponseBadRequest, HttpResponseRedirect,
                         HttpResponse, Http404)
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST

from tcc import api
from tcc.forms import CommentForm
from tcc.utils import get_content_types

# jinja
from coffin.shortcuts import render_to_response
'''Monkeypatch Django to mimic Jinja2 behaviour'''
from django.utils import safestring
if not hasattr(safestring, '__html__'):
    safestring.SafeString.__html__ = lambda self: str(self)
    safestring.SafeUnicode.__html__ = lambda self: unicode(self)


def _get_tcc_index(comment):
    return reverse('tcc_index',
                   args=[comment.content_type_id, comment.object_pk])


def _get_comment_form(content_type_id, object_pk, data=None):
    if not content_type_id or int(content_type_id) not in get_content_types():
        raise Http404()
    ct = get_object_or_404(ContentType, pk=content_type_id)
    try:
        target = ct.get_object_for_this_type(pk=object_pk)
    except ObjectDoesNotExist:
        raise Http404()
    initial = {'content_type': ct.id, 'object_pk': object_pk}
    form = CommentForm(target, data, initial=initial)
    return form


def index(request, content_type_id, object_pk):
    comments = api.get_comments_limited(
        content_type_id, object_pk
        ).extra(select={
            'sortdate': 'CASE WHEN tcc_comment.parent_id is null ' \
                ' THEN tcc_comment.submit_date ELSE T3.submit_date END'}
                ).order_by('-sortdate', 'path')
    form = _get_comment_form(content_type_id, object_pk)
    context = RequestContext(request, {'comments': comments, 'form': form })
    return render_to_response('tcc/index.html', context)


def replies(request, parent_id):
    comments = api.get_comment_replies(parent_id)
    context = RequestContext(request, {'comments': comments})
    return render_to_response('tcc/replies.html', context)


def thread(request, thread_id):
    # thead_id here should be the root_id of the thread (even though
    # any comment_id will work) so the entire thread can cached *and*
    # invalidated with one entry
    comments = api.get_comment_thread(thread_id)
    if not comments:
        raise Http404()
    rootcomment = comments[0]
    form = _get_comment_form(rootcomment.content_type_id, rootcomment.object_pk)
    context = RequestContext(request, {'comments': comments, 'form': form})
    return render_to_response('tcc/index.html', context)


@login_required
@require_POST
def post(request):
    data = request.POST.copy()
    content_type_id = data.get('content_type', None)
    object_pk = data.get('object_pk', None)
    # inject the user
    data['user'] = request.user.id
    form = _get_comment_form(content_type_id, object_pk, data)
    if form.is_valid():
        parent = form.cleaned_data.get('parent', None)
        if parent:
            parent_id = parent.id
        else:
            parent_id = None
        message = form.cleaned_data.get('comment', '')
        comment = api.post_comment(content_type_id=content_type_id,
                                   object_pk=object_pk,
                                   user_id=request.user.id,
                                   comment=message,
                                   parent_id=parent_id)
        if comment:
            if request.is_ajax():
                context = RequestContext(request, {'c': comment})
                return render_to_response('tcc/comment.html', context)
            next = form.cleaned_data['next']
            if not next:
                next = comment.get_absolute_url()
            return HttpResponseRedirect(next)
    if request.is_ajax():
        return HttpResponseBadRequest(simplejson.dumps(form.errors),
                                      mimetype="application/json")
    else:
        # TODO: what to do here?
        next = data.get('next', None)
        if not next:
            next = request.META['HTTP_REFERER']
        return HttpResponseRedirect(next)


@login_required
@require_POST
def flag(request):
    return HttpResponse('TODO')


@login_required
@require_POST
def unflag(request):
    return HttpResponse('TODO')


@login_required
@require_POST
def approve(request, comment_id):
    comment = api.approve_comment(comment_id, request.user)
    if comment:
        return HttpResponseRedirect(comment.get_absolute_url())
    raise Http404()


@login_required
@require_POST
def disapprove(request, comment_id):
    comment = api.disapprove_comment(comment_id, request.user)
    if comment:
        tcc_index = _get_tcc_index(comment)
        return HttpResponseRedirect(tcc_index)
    raise Http404()


@login_required
@require_POST
def remove(request, comment_id):
    comment = api.remove_comment(comment_id, request.user)
    if comment:
        if request.is_ajax():
            return HttpResponse() # 200 OK
        tcc_index = _get_tcc_index(comment)
        return HttpResponseRedirect(tcc_index)
    raise Http404()


@login_required
@require_POST
def restore(request, comment_id):
    comment = api.restore_comment(comment_id, request.user)
    if comment:
        return HttpResponseRedirect(comment.get_absolute_url())
    raise Http404()
