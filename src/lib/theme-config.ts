export const THEME_KEY = "endurace-theme";
export const THEME_EVENT = "endurace-theme-change";
/** Runs before hydration so a saved dark theme does not flash a light canvas. */
export const THEME_BOOTSTRAP = `(function(){var t;try{t=localStorage.getItem("${THEME_KEY}")}catch(e){}if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t})()`;
