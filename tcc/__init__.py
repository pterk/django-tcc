from django.core.urlresolvers import reverse

from tcc.models import Comment
from tcc.forms import CommentForm


# django comment-app api
def get_model():
    return Comment


def get_form():
    return CommentForm


def get_form_target():
    return reverse('tcc_post')


def get_flag_url(comment):
    return reverse('tcc_flag', args=[comment.id])


def get_delete_url(comment):
    return reverse('tcc_remove', args=[comment.id])


def get_approve_url(comment):
    return reverse('tcc_approve', args=[comment.id])


# extra methods
def get_unflag_url(comment):
    return reverse('tcc_unflag', args=[comment.id])


def get_undelete_url(comment):
    return reverse('tcc_restore', args=[comment.id])


def get_disapprove_url(comment):
    return reverse('tcc_disapprove', args=[comment.id])
