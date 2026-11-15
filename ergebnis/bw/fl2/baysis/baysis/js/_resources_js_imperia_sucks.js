$( document ).ready(function() {
    if(window.location.href.includes('internet/verdat/svz')) {
        $('#app').removeClass('module');
    }
	
	if(window.location.href.includes('internet/verdat/svz/kennwerte/index.html')) {
        $('.modContent').css('transform', 'translate(-56.7%,10%)');
		$('.modContent').css('margin-bottom', '150px');
    }
});