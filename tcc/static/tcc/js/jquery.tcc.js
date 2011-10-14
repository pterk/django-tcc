// closure
(function($) {

    // private vars (within the closure)
    var opts;
    var JSMINUTE = 60*1000; // milliseconds
    var JSHOUR = 60*JSMINUTE
    var JSDAY = 24*JSHOUR

    // plugin definition
    $.fn.tcc = function(options){
        // build main options before element iteration
        opts = $.extend({}, $.fn.tcc.defaults, options);
        // iterate and reformat each matched element
        return this.each(function(){
            init();
        });
    };

    // defaults
    $.fn.tcc.defaults = {
        user_id: null,
        user_name: null,
        staff: false,
        csrf_token: '',
        timeout: 5000,
    };

    // private function for debugging
    function debug(msg) {
        if(window.console && window.console.log){
            window.console.log(msg);
        };
    };

    function handleError(context, jqXHR, textStatus, errorThrown){
        $('body').css({'cursor': 'auto'});
        $('.notify', context).text('');
        try {
            listErrors(context, $.parseJSON(jqXHR.responseText));
        } catch (e) {
            listErrors(context, {'err': [textStatus]});
        }
    }

    function listErrors(frm, errors){
        if($('ul.errors', frm).length == 0){
            $(frm).prepend('<ul class="errors"/>');
        };
        $('ul.errors', frm).empty();
        $.each(errors, function(field, msgs){
            $.each(msgs, function(idx, msg){
                var li = '<li>' + msg + '</li>';
                $('ul.errors', frm).append(li);
            });
        });
    };

    function isScrolledIntoView(elem){
        var docViewTop = $(window).scrollTop();
        var docViewBottom = docViewTop + $(window).height();
        var elemTop = $(elem).offset().top;
        var elemBottom = elemTop + $(elem).height();
        return ((elemBottom >= docViewTop) && (elemTop <= docViewBottom));
    };

    function hijax(){

        // showall is enabled for everyone
        $('a.showall').click(function(){
            var parent = $(this).parent();
            if($('ul.replies', parent).length == 0){ $(parent).append('<ul class="replies"/>');};
            var ul = $('ul.replies', parent).first();
            $.ajax({
                url: $(this).attr('href'),
                timeout: opts.timeout,
                error: function(){
                    $('ul.replies', parent).after(
                        '<span class="error">'
                            + gettext('There was an error communicating with the server')
                            + '</span>');
                },
                success: function(data){
                    $(ul).html(data);
                    apply_hooks();
                }
            });
            $(this).remove();
            return false;
        });

        // pagination
        $('#tcc .pagination a').click(function(){
            $.ajax({
                url: $(this).attr('href'),
                timeout: opts.timeout,
                error: function(){
                    $('#tcc').append(
                        '<span class="error">'
                            + gettext('There was an error communicating with the server')
                            + '</span>');
                },
                success: function(data){
                    $('#tcc').replaceWith(data);
                    hijax();
                    apply_hooks();
                }
            });
            return false;
        });

        if ( opts.user_id ) {
            // run this only once
            var frm = $('#tcc form').first();
            frm.css({"display": 'block'});
            $(frm).submit(function(){
                $('body').css({'cursor': 'wait'});
                $('.notify', frm).text('Posting your comment...');
                $('input[name="csrfmiddlewaretoken"]', this).val(opts.csrf_token);
                // clean up any pre-existing errors (from previous submit)
                $('ul.errors', frm).remove();
                $.ajax({
                    type: 'POST',
                    timeout: opts.timeout,
                    url: $(this).attr('action'),
                    data: $(this).serialize(),
                    context: frm,
                    error: function(jqXHR, textStatus, errorThrown){
                        handleError(frm, jqXHR, textStatus, errorThrown);
                    },
                    success: function(data){
                        $('body').css({'cursor': 'auto'});
                        $('.notify', frm).text('');
                        if( $('#tcc ul.comments li').length == 0){
                            // There were no comments so far, so this is the first comment
                            // Remove the 'no comments yet' message
                            $('#tcc ul.comments').children().not('form').remove();
                            $('#tcc ul.comments').append(data);
                        } else {
                            $('#tcc ul.comments li').first().before(data);
                        }
                        apply_hooks();
                        $('#id_comment', frm).val('');
                        var latest = $('#tcc ul.comments li.comment').first();
                        if(!isScrolledIntoView(latest)){
                            $(document).scrollTop($(latest).offset().top-300);
                        };

                    }
                });
                return false;
            });
        } else {
            // Not logged in
            $('#no-comment-form').css({'display': 'inline'});
        };

    }

    function apply_hooks(){

        // highlight a thread
        if(window.location.hash){
            $('a[name="' + window.location.hash.slice(1) +'"]').each(function(){
                $(this).parent().addClass('highlight');
            });
        };

        // humanize
        if(opts.user_name){
            $('.c-user').filter(function(){
                return $(this).text() == opts.user_name
            }).text(gettext('You'));
        };

        function make_local_time(dte){
            var offset = -1 * new Date().getTimezoneOffset();
            return new Date(dte.valueOf()+(offset*JSMINUTE));
        };

        function is_nowish(dte){
            // This is localtime (for the browser)
            var now = new Date();
            return (now-dte < JSMINUTE*5);
        };

        function date_format(dte){
            var y=dte.getFullYear(), m=dte.getMonth()+1, d=dte.getDate(),
            h = dte.getHours(), m = dte.getMinutes(), s = dte.getSeconds();
            if (d < 10) { d = '0' + d; };
            if (m < 10) { m = '0' + m; };
            if (s < 10) { s = '0' + s; };
            return [y,m,d].join('-')+' '+[h, m].join(':');
        };

        function days_ago(dte){
            var now = new Date();
            return parseInt((now-dte)/JSDAY);
        };

        $('span.c-date').not('.humanized').each(function(){
            try {
                var datetime = $(this).text().split(' ');
                var dte = datetime[0].split('-');
                var tme = datetime[1].split(':');

                // Be sure to use parseInt with Base 10 or '08' and
                // '09' will be interpreted as 0 and that will produce
                // `much weirdness`

                // This is a UTC time
                dte = new Date(parseInt(dte[0], 10), (parseInt(dte[1], 10) - 1), parseInt(dte[2], 10),
                               parseInt(tme[0], 10), parseInt(tme[1], 10), 0);
                // Now it's localtime
                dte = make_local_time(dte);

                var humandate = '';
                var n = days_ago(dte);

                switch(true){
                case n==0:
                    if (is_nowish(dte)) {
                        humandate = gettext('just now');
                    } else {
                        humandate = gettext('today');
                    };
                    break;
                case n==1:
                    humandate = gettext('yesterday');
                    break;
                case n >1 && n < 7:
                    humandate = n + gettext(' days ago');
                    break;
                case n > 6 && n < 15:
                    humandate = gettext('last week');
                    break;
                default:
                    humandate = date_format(dte);
                };
                $(this).text(humandate);
                $(this).addClass('humanized');
            } catch (e) {
                debug(e);
            };
        });

        if(opts.user_id){

            $('#tcc form').first().css({'display': 'inline'});
            $('#tcc p').first().css({'display': 'none'});

            $('.comment-remove-'+opts.user_id).css({'display': 'inline'});
            if (opts.staff) {
                $('.comment-remove').css({'display': 'inline'});
            }
            $('.comment-remove').click(function(){
                var parent = $(this).closest('li.comment');
                $('form', parent).remove();
                var action = $('a', this).attr('href');
                var frm = $('.remove-form').last().clone();
                $('a.remove-cancel', frm).click(function(){
                    frm.remove();
                    return false;
                });
                frm.submit(function(){
                    $('body').css({'cursor': 'wait'});
                    $('.notify', frm).text('removing...');
                    $('input[name="csrfmiddlewaretoken"]', this).val(opts.csrf_token);
                    $.ajax({
                        type: 'POST',
                        timeout: opts.timeout,
                        url: action,
                        data: $(this).serialize(),
                        error: function(jqXHR, textStatus, errorThrown){
                            handleError(frm, jqXHR, textStatus, errorThrown);
                        },
                        success: function(){
                            $('body').css({'cursor': 'auto'});
                            $('.notify', frm).text('');
                            frm.remove();
                            parent.remove();
                        }
                    });
                    return false;
                });
                frm.css({'display': 'block'});
                parent.append(frm);
                return false;
            });

            $('.comment-unsubscribe-'+opts.user_id).css({'display': 'inline'});
            $('.comment-unsubscribe').click(function(){
                var parent = $(this).closest('li.comment');
                $('form', parent).remove();
                var action = $('a', this).attr('href');
                var frm = $('.unsubscribe-form').last().clone();
                $('a.unsubscribe-cancel', frm).click(function(){
                    frm.remove();
                    return false;
                });
                frm.submit(function(){
                    $('body').css({'cursor': 'wait'});
                    $('.notify', frm).text('unsubscribing...');
                    $('input[name="csrfmiddlewaretoken"]', this).val(opts.csrf_token);
                    $.ajax({
                        type: 'POST',
                        timeout: opts.timeout,
                        url: action,
                        data: $(this).serialize(),
                        error: function(jqXHR, textStatus, errorThrown){
                            handleError(frm, jqXHR, textStatus, errorThrown);
                        },
                        success: function(){
                            $('body').css({'cursor': 'auto'});
                            $('.notify', frm).text('');
                            frm.remove();
                            $('.comment-unsubscribe', parent).remove();
                        }
                    });
                    return false;
                });
                frm.css({'display': 'block'});
                parent.append(frm);
                return false;
            });

            $('.comment-reply').css({'display': 'inline'});
            $('.comment-reply').click(function(){
                var parent = $(this).closest('li.comment');
                $('form', parent).remove();
                var frm = $('#tcc form').first().clone(false);
                $('ul.errors', frm).empty();
                $('#id_parent', frm).val($('a', this).attr('id').slice(5));
                $(frm).submit(function(){
                    $('body').css({'cursor': 'wait'});
                    $('.notify', frm).text('Posting your comment...');
                    $('input[name="csrfmiddlewaretoken"]', this).val(opts.csrf_token);
                    $.ajax({
                        type: 'POST',
                        timeout: opts.timeout,
                        url: $(this).attr('action'),
                        data: $(this).serialize(),
                        error: function(jqXHR, textStatus, errorThrown){
                            handleError(frm, jqXHR, textStatus, errorThrown);
                        },
                        success: function(comment){
                            if($('ul.replies', parent).length == 0){ $(parent).append('<ul class="replies"/>');}
                            $('ul.replies', parent).append(comment);
                            $('body').css({'cursor': 'auto'});
                            $('.notify', frm).text('');
                            frm.remove();
                            apply_hooks();
                        }
                    });
                    return false;
                });
                parent.append(frm);
                if(!isScrolledIntoView(frm)){
                    $(document).scrollTop($(frm).offset().top-300);
                };
                $('#id_comment', frm).focus();
                return false;
            });
        } else {

            // No user_id / not logged in
            $('#tcc form').first().css({'display': 'none'});
            $('#tcc p').first().css({'display': 'inline'});

        };
    };

    function init(){

        hijax();

        apply_hooks();

    };

})(jQuery);
