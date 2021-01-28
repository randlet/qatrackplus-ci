(function(){

"use strict";

/* globals jQuery, window, QAUtils, require, document */

require(['jquery', 'lodash'], function ($, _) {

    var csrf_token = $("input[name=csrfmiddlewaretoken]").val();

    function csrfSafeMethod(method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }
    function sameOrigin(url) {
        // test that a given url is a same-origin URL
        // url could be relative or scheme relative or absolute
        var host = document.location.host; // host + port
        var protocol = document.location.protocol;
        var sr_origin = '//' + host;
        var origin = protocol + sr_origin;
        // Allow absolute or scheme relative URLs to same origin
        return (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
            (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
            // or any other URL that isn't scheme relative or absolute i.e relative.
            !(/^(\/\/|http:|https:).*/.test(url));
    }
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && sameOrigin(settings.url)) {
                // Send the token to same-origin, relative URLs only.
                // Send the token only if the method warrants CSRF protection
                // Using the CSRFToken value acquired earlier
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
        }
    });

    $(".test-selected-toggle").eq(0).hide();
    $(".bulk-review-all").eq(0).hide();

    $("input.test-selected-toggle").on("change", function (e) {
        $("input.test-selected-toggle").not($(this)).prop("checked", $(this).is(":checked"));
        $(this).closest("table").find("input.test-selected").prop("checked", $(this).is(":checked"));
    });

    var headers = _.map($("#listable-table-fault_list_unreviewed tr:first th"), function(el){
        return el.innerText.toLowerCase();
    });
    var siteIdx = headers.indexOf("site");
    var unitIdx = headers.indexOf("unit");
    var faultTypeIdx = headers.indexOf("fault type");

    $("#submit-review").click(function(){
        var $tableBody = $("#instance-summary tbody");

        var $rows = $("#listable-table-fault_list_unreviewed tbody tr td input:checkbox:checked").filter(function(i, v){
            return $(v).val() !== "";
        }).parents("tr");

        var counter = {};
        $rows.each(function(idx, el){
            var $el = $(el);
            var children = $el.children();
            var site = siteIdx >= 0 ? (children[siteIdx].innerText || "Other") + ": " : "";
            var unit = site + children[unitIdx].innerText;
            var ft = children[faultTypeIdx].innerText;
            var key = [ft, unit].join("||");

            if (key in counter){
                counter[key] += 1;
            } else {
                counter[key] = 1;
            }
        });

        var $tbody = $("#instance-summary tbody");
        $tbody.html("");
        var sorted = _(_.keys(counter)).sortBy(function(k){return counter[k];}).reverse();
        sorted.each(function(k){
            var count = counter[k];
            if (count <= 0){
                return;
            }
            var split = k.split("||");
            var row = "<tr><td>" + split[0] + "</td><td>" + split[1] + "</td><td>" + count + "</td></tr>";
            $tbody.append(row);
        });
    });


    $("#confirm-update").click(function(e){

        var toUpdate = _.map($("#listable-table-fault_list_unreviewed tbody tr td input:checkbox:checked"), function(el){
            return $(el).data("fault");
        });
        var data = {faults: toUpdate};

        $.ajax({
            type:"POST",
            url: QAURLs.FAULT_BULK_REVIEW,
            data: data,
            dataType:"json",
            success: function (result) {
                if (result.ok){
                    location.reload();
                }else{
                    $("#bulk-review-msg").html('<span style="color: red"><em>Sorry reviewing the faults failed.</em></span>');
                }
            },
            traditional:true,
            error: function(e, data){
                $("#bulk-review-msg").html('<span style="color: red"><em>Sorry reviewing the faults failed.</em></span>');
            }
        });

        e.preventDefault();

    });
});

})(); /* use strict IIFE */
