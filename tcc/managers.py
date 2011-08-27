from django.db.models import Manager, F, Q

from tcc.utils import get_content_types


class CurrentCommentManager(Manager):
    """ Returns only approved comments that are not (marked as) removed

    Also filters is_public == False for backwards compatibility

    Also only returns comments whose CONTENT_TYPES are allowed
    """
    def get_query_set(self, *args, **kwargs):
        return super(CurrentCommentManager, self).get_query_set(
            *args, **kwargs).filter(
            is_removed=False, is_approved=True, is_public=True,
            content_type__id__in=get_content_types()
            ).filter(
                Q(parent__isnull=True) | \
                    Q(parent__is_removed=False,
                      parent__is_approved=True,
                      parent__is_public=True))


class LimitedCurrentCommentManager(CurrentCommentManager):
    def get_query_set(self, *args, **kwargs):
        return super(LimitedCurrentCommentManager, self).get_query_set(
            *args, **kwargs).filter(
            Q(parent__isnull=True) | Q(parent__limit__lte=F('submit_date')))


class RemovedCommentManager(Manager):
    """ Returns onle comments marked as removed

    To be able to unmark them...
    """
    def get_query_set(self, *args, **kwargs):
        return super(RemovedCommentManager, self).get_query_set(
            *args, **kwargs).filter(
            is_removed=True)


class DisapprovedCommentManager(Manager):
    """ Returns disapproved (unremoved) comments

    To be able to unmark them...
    """
    def get_query_set(self, *args, **kwargs):
        return super(DisapprovedCommentManager, self).get_query_set(
            *args, **kwargs).filter(
            is_removed=False, is_approved=False)
