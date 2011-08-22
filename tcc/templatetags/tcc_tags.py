from django import template
from django.contrib.contenttypes.models import ContentType

from coffin.template.loader import render_to_string

from tcc import api
from tcc.forms import CommentForm
from tcc.settings import CONTENT_TYPES

register = template.Library()


@register.simple_tag(takes_context=True)
def get_comments_for_object(context, object, next=None):
    ct = ContentType.objects.get_for_model(object)
    if ct.id not in CONTENT_TYPES:
        return 'Not supported'
    comments = api.get_comments(ct.id, object.pk)
    comments = comments.order_by('-submit_date')
    initial = {'content_type': ct.id,
               'object_pk': object.pk,
               'next': next,
               }
    form = CommentForm(object, initial=initial)
    context.update({'comments': comments, 'form': form})
    return render_to_string('tcc/list-comments.html',
                            context_instance=context)
