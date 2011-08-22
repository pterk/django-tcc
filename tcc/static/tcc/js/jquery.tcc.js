// closure
(function($) {

    // private vars (within the closure)
    var opts;
    var JSMINUTE = 60*1000; // milliseconds
    var JSHOUR = 60*JSMINUTE
    var JSDAY = 24*JSHOUR
    //
    // plugin definition
    //
    $.fn.tcc = function(options){
        // build main options before element iteration
        opts = $.extend({}, $.fn.tcc.defaults, options);
        // iterate and reformat each matched element
        return this.each(function(){
            init();
        });
    };
                        
    // Default width and height for the editor
    $.fn.tcc.defaults = {
        user_id: null,
        user_name: null,
    };

    //
    // private function for debugging
    //
    function debug(msg) {
        if(window.console && window.console.log){
            window.console.log(msg);
        };
    };

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

    function apply_hooks(){

        // highlight a thread
        if(window.location.hash){
            debug(window.location.hash);
            $('a[name="' + window.location.hash.slice(1) +'"]').each(function(){
                $(this).parent().addClass('highlight');
            });
        };

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
            var y=dte.getYear(), m=dte.getMonth(), d=dte.getDay(),
            h = dte.getHours(), m = dte.getMinutes(), s = dte.getSeconds();
            if (d < 10) { d = '0' + dd; };
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
                // This is a UTC time
                dte = new Date(parseInt(dte[0]), parseInt(dte[1]) - 1, parseInt(dte[2]),
                               parseInt(tme[0]), parseInt(tme[1]));
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
                // pass
            };
        });

        if(opts.user_id){
            $('.comment-remove-'+opts.user_id).css({'display': 'inline'});
            $('.comment-remove').click(function(){
                var parent = $(this).parent().parent();
                $('form', parent).remove();
                var action = $('a', this).attr('href');
                var frm = $('.remove-form').last().clone();
                $('a.remove-cancel', frm).click(function(){ 
                    frm.remove(); 
                    return false;
                });
                frm.submit(function(){
                    $.post(action, $(this).serialize(), function(){
                        frm.remove();
                        parent.remove();
                    });
                    $(frm).ajaxError(function(ev, xhr, req, error_message){
                        listErrors(frm, $.parseJSON(xhr.responseText));
                    });
                    return false;
                });
                frm.css({'display': 'block'});
                parent.append(frm);
                return false;
            });

            $('.comment-reply').css({'display': 'inline'});
            $('.comment-reply').click(function(){
                var parent = $(this).parent().parent();
                $('form', parent).remove();
                var frm = $('#tcc form').first().clone();
                $('#id_parent', frm).val($('a', this).attr('id').slice(5));
                $(frm).submit(function(){
                    $.post($(this).attr('action'), $(this).serialize(), function(comment){
                        frm.remove();
                        if($('ul.replies', parent).length == 0){ $(parent).append('<ul class="replies"/>');}
                        $('ul.replies', parent).append(comment);
                        apply_hooks();
                    });
                    $(frm).ajaxError(function(ev, xhr, req, error_message){
                        listErrors(frm, $.parseJSON(xhr.responseText));
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
        };
    };

    function init(){
        // showall is enable for everyone
        $('a.showall').click(function(){
            var parent = $(this).parent();
            if($('ul.replies', parent).length == 0){ $(parent).append('<ul class="replies"/>');};
            var ul = $('ul.replies', parent).first();
            $.get($(this).attr('href'), function(data){
                $(ul).html(data);
                apply_hooks();
            });
            $(this).remove();
            return false;
        });

        apply_hooks();

        if ( opts.user_id ) {
            // run this only once
            var frm = $('#tcc form').first();
            $(frm).submit(function(){
                $.post($(this).attr('action'), $(this).serialize(), function(data){
                    $('ul#tcc li').first().before(data);
                    apply_hooks();
                    $('#id_comment', frm).val('');
                    var latest = $('ul#tcc li.comment').first();
                    if(!isScrolledIntoView(latest)){
                        $(document).scrollTop($(latest).offset().top-300);
                    };
                });
                $(frm).ajaxError(function(ev, xhr, req, error_message){
                    listErrors(frm, $.parseJSON(xhr.responseText));
                });
                return false;
            });
        };
    };

})(jQuery);
