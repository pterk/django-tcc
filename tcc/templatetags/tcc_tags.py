from django import template
from django.contrib.contenttypes.models import ContentType

from coffin.template.loader import render_to_string

from tcc import api
from tcc.forms import CommentForm
from tcc.settings import SORTORDER
from tcc.utils import get_content_types
from tcc.views import _get_comment_form

register = template.Library()


@register.simple_tag(takes_context=True)
def get_comments_for_object(context, object, next=None):
    ct = ContentType.objects.get_for_model(object)
    request = context['request']
    initial = {'content_type': ct.id,
               'object_pk': object.pk,
               'next': next,
               }
    form = CommentForm(object, initial=initial)
    thread_id = request.GET.get('cpermalink', None)
    if thread_id:
        comments = api.get_comment_thread(thread_id)
    else:
        comments = api.get_comments_limited(ct.id, object.pk)
    if not comments:
        comments = []
    else:
        comments = comments.order_by('-%s' % SORTORDER, 'path')
    context.update({'comments': comments, 'form': form})
    return render_to_string('tcc/list-comments.html',
                            context_instance=context)
