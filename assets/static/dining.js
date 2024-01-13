/*
 * UX utility: add the `remember-scroll` class to a form element on the page to restore
 * the scroll position after a POST redirect.
 */
window.addEventListener('load', function () {
    // If there is a saved scroll position, apply it
    let scroll = sessionStorage.getItem('scrollPosition');
    if (scroll) {
        window.scroll(0, parseFloat(scroll));
    }

    // Clear the value
    sessionStorage.removeItem('scrollPosition');

    // On submit of a form, save the value
    let forms = document.getElementsByClassName("remember-scroll");
    for (let i = 0; i < forms.length; i++) {
        forms[i].addEventListener('submit', function (event) {
            sessionStorage.setItem('scrollPosition', window.scrollY.toString());
        })
    }
});
