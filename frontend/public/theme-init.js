;(() => {
  try {
    const storedTheme = window.localStorage.getItem('theme')
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const theme =
      storedTheme === 'dark' || storedTheme === 'light'
        ? storedTheme
        : prefersDark
          ? 'dark'
          : 'light'

    const root = document.documentElement
    const themeColor = theme === 'dark' ? '#08111b' : '#eef4f8'
    root.setAttribute('data-theme', theme)
    root.style.colorScheme = theme

    const metaThemeColor = document.querySelector('meta[name="theme-color"]')
    if (metaThemeColor) metaThemeColor.setAttribute('content', themeColor)
  } catch {}
})()
