try:
    set
except NameError:
    from sets import Set as set

from django.core.paginator import Paginator, Page, InvalidPage
from django.db.models import F
from django.http import Http404

from coffin import template
from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.exceptions import TemplateSyntaxError

from tcc import settings

register = template.Library()

# Most of the code below is borrowed from the django_pagination module by James Tauber and Pinax Team,
# http://pinaxproject.com/docs/dev/external/pagination/index.html


class ParentCommentPaginator(Paginator):
    def page(self, number):
        "Returns a Page object for the given 1-based page number."
        number = self.validate_number(number)
        if self.count == 0:
            return Page(self.object_list, number, self)
        bottom = (number - 1) * self.per_page
        # This results in a query to the database ...
        bottomdate = getattr(self.parentcomments[bottom], settings.SORTORDER)
        try:
            # This too results in a query to the database ...
            top = self.parentcomments[bottom+self.per_page-1].sortdate
            kwargs = {'%s__range' % settings.SORTORDER: (top, bottomdate)}
            object_list = self.object_list.filter(**kwargs)
        except IndexError:
            kwargs = {'%s__lte' % setting.SORTORDER: bottomdate}
            object_list = self.object_list.filter(**kwargs)
        # And another (final) call to the database 
        return Page(object_list, number, self)

    def _get_count(self):
        "Returns the total number of objects, across all pages."
        if self._count is None:
            try:
                self.parentcomments = self.object_list.filter(parent__isnull=True)
                self._count = self.parentcomments.count()
            except (AttributeError, TypeError):
                # AttributeError if object_list has no count() method.
                # TypeError if object_list.count() requires arguments
                # (i.e. is of type list).
                self._count = len(self.object_list)
        return self._count
    count = property(_get_count)
        

class AutopaginateExtension(Extension):
    """ 
        Applies pagination to the given dataset (and saves truncated dataset to the context variable), 
        sets context variable with data enough to build html for paginator
        
        General syntax:

        {% autopaginate dataset [as ctx_variable] %}
        if "as" part is omitted, trying to save truncated dataset back to the original
        context variable.
        Pagination data is saved to the NAME_pages context variable, where NAME is
        original name of the dataset or ctx_variable
    """
    tags = set(['autopaginate'])
    default_kwargs = {
        'per_page': settings.PER_PAGE,
        'orphans': settings.PAGE_ORPHANS,
        'window': settings.PAGE_WINDOW,
        'hashtag': '',
        'prefix': '',
        }

    def parse(self, parser):
        lineno = parser.stream.next().lineno
        object_list = parser.parse_expression()
        if parser.stream.skip_if('name:as'):
            name = parser.stream.expect('name').value
        elif hasattr(object_list, 'name'):
            name = object_list.name
        else:
            raise TemplateSyntaxError("Cannot determine the name of objects you want to paginate, use 'as foobar' syntax", lineno)


        kwargs = [] # wait... what?
        loops = 0
        while parser.stream.current.type != 'block_end':
            lineno = parser.stream.current.lineno
            if loops:
                parser.stream.expect('comma')
            key = parser.parse_assign_target().name
            if key not in self.default_kwargs.keys():
                raise TemplateSyntaxError(
                    "Unknown keyword argument for autopaginate. Your options are: %s" % (
                        ", ".join(self.default_kwargs.keys())
                        ))
            parser.stream.expect('assign')
            value = parser.parse_expression()
            kwargs.append(nodes.Keyword(key, value)) #.set_lineno(lineno)) # like so?
            loops += 1

        return [
            nodes.Assign(nodes.Name(name + '_pages', 'store'), 
                         self.call_method('_render_pages', [object_list, nodes.Name('request', 'load')], kwargs)
            ).set_lineno(lineno),

            nodes.Assign(nodes.Name(name, 'store'), 
                nodes.Getattr(nodes.Name(name + '_pages', 'load'), 'object_list', nodes.Impossible())
            ).set_lineno(lineno),
        ]
        
    def _render_pages(self, objs, request, **kwargs):
        mykwargs = self.default_kwargs.copy()
        mykwargs.update(kwargs)
        prefix = mykwargs.pop('prefix')
        window = mykwargs.pop('window')
        hashtag = mykwargs.pop('hashtag')
        try:
            paginator = ParentCommentPaginator(objs, **mykwargs)

            key = 'page'
            if prefix:
                key = prefix + key
            try:
                try:
                    pageno = int(request.GET[key])
                except (KeyError, ValueError, TypeError):
                    pageno = 1
                page_obj = paginator.page(pageno)
            except InvalidPage:
                raise Http404('Invalid page requested.  If DEBUG were set to ' +
                        'False, an HTTP 404 page would have been shown instead.')

            page_range = paginator.page_range
            # Calculate the record range in the current page for display.
            records = {'first': 1 + (page_obj.number - 1) * paginator.per_page}
            records['last'] = records['first'] + paginator.per_page - 1
            if records['last'] + paginator.orphans >= paginator.count:
                records['last'] = paginator.count
            # First and last are simply the first *n* pages and the last *n* pages,
            # where *n* is the current window size.
            first = set(page_range[:window])
            last = set(page_range[-window:])
            # Now we look around our current page, making sure that we don't wrap
            # around.
            current_start = page_obj.number-1-window
            if current_start < 0:
                current_start = 0
            current_end = page_obj.number-1+window
            if current_end < 0:
                current_end = 0
            current = set(page_range[current_start:current_end])
            pages = []
            # If there's no overlap between the first set of pages and the current
            # set of pages, then there's a possible need for elusion.
            if len(first.intersection(current)) == 0:
                first_list = list(first)
                first_list.sort()
                second_list = list(current)
                second_list.sort()
                pages.extend(first_list)
                diff = second_list[0] - first_list[-1]
                # If there is a gap of two, between the last page of the first
                # set and the first page of the current set, then we're missing a
                # page.
                if diff == 2:
                    pages.append(second_list[0] - 1)
                # If the difference is just one, then there's nothing to be done,
                # as the pages need no elusion and are correct.
                elif diff == 1:
                    pass
                # Otherwise, there's a bigger gap which needs to be signaled for
                # elusion, by pushing a None value to the page list.
                else:
                    pages.append(None)
                pages.extend(second_list)
            else:
                unioned = list(first.union(current))
                unioned.sort()
                pages.extend(unioned)
            # If there's no overlap between the current set of pages and the last
            # set of pages, then there's a possible need for elusion.
            if len(current.intersection(last)) == 0:
                second_list = list(last)
                second_list.sort()
                diff = second_list[0] - pages[-1]
                # If there is a gap of two, between the last page of the current
                # set and the first page of the last set, then we're missing a 
                # page.
                if diff == 2:
                    pages.append(second_list[0] - 1)
                # If the difference is just one, then there's nothing to be done,
                # as the pages need no elusion and are correct.
                elif diff == 1:
                    pass
                # Otherwise, there's a bigger gap which needs to be signaled for
                # elusion, by pushing a None value to the page list.
                else:
                    pages.append(None)
                pages.extend(second_list)
            else:
                differenced = list(last.difference(current))
                differenced.sort()
                pages.extend(differenced)
            to_return = {
                'pages': pages,
                'records': records,
                'page_obj': page_obj,
                'prefix': prefix,
                'object_list': page_obj.object_list,
                'paginator': paginator,
                'hashtag': hashtag,
                'is_paginated': paginator.count > (paginator.per_page + paginator.orphans),
            }

            getvars = request.GET.copy()
            if key  in getvars:
                del getvars[key]
            if len(getvars.keys()) > 0:
                to_return['getvars'] = "&%s" % getvars.urlencode()
            else:
                to_return['getvars'] = ''

            return to_return
        except KeyError, AttributeError:
            return {}


register.tag(AutopaginateExtension)
