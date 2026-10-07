/** Dark-only site: pins the theme before hydration so nothing renders with the light palette. */
export const THEME_BOOTSTRAP = `document.documentElement.dataset.theme="dark";document.documentElement.style.colorScheme="dark";`;
