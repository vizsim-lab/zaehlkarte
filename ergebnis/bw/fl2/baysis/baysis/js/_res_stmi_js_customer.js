/* Fuer eigenes JS */

/* Matomo Zustimmung */
function setMatomoConsent() {
    _paq.push(['rememberConsentGiven']);
    setConsentText('yes');
}

function declineMatomoConsent() {
    _paq.push(['forgetConsentGiven']);
    setConsentText('no');
}

function setConsentText(consent) {
    if (consent == "no" && document.getElementById('matomo_consent')) {
        document.getElementById('matomo_consent').innerHTML =
            'Derzeit wird Ihr Besuch nicht von Matomo Analytics erfasst.<br /> ' +
            'Wenn Sie damit einverstanden sind, dass wir zu Analysezwecken Cookies setzen und die gewonnen Daten ' +
            'verarbeiten, klicken Sie bitte auf den Button "Webanalyse akzeptieren". Sie können Ihre Einwilligung ' +
            'später jederzeit mit Wirkung für die Zukunft <strong>widerrufen</strong>.' +
            '<p style="text-align:center;"><button class="icon save-selected" title="Webanalyse akzeptieren" onClick="setMatomoConsent()">' +
            'Webanalyse akzeptieren</button></p>';
    }
    if (consent == "yes" && document.getElementById('matomo_consent')) {
        document.getElementById('matomo_consent').innerHTML =
            'Derzeit wird Ihr Besuch von Matomo Analytics erfasst.<br /> ' +
            'Durch Klick auf den Button „Webanalyse nicht zulassen“ können ' +
            'Sie ihre Einwilligung mit Wirkung für die Zukunft <strong>widerrufen</strong>.' +
            '<p style="text-align:center;"><button class="icon save-selected" title="Webanalyse nicht zulassen" onClick="declineMatomoConsent()">' +
            'Webanalyse nicht zulassen</button></p>';}

}

$(document).ready(function() {

    if (document.cookie.indexOf('mtm_consent=') == -1) {
        setConsentText('no');
    } else {
        setConsentText('yes');
    }
});


