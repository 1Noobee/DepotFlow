/** Tailwind v3.4 config. See assets/tailwind.input.css for how to rebuild the stylesheet. */
module.exports = {
  content: [
    './templates/**/*.html',
    './*/templates/**/*.html',
    './core/static/core/js/*.js',
    './*/forms.py',                       // widget classes set in Python
    './assets/crispy-tailwind-tokens.html', // classes used by the crispy-tailwind form pack
  ],
  theme: {
    extend: {
      colors: {
        'depot-ink': '#181818',
        'depot-paper': '#FAFAFA',
        'depot-teal': '#E4002B',
        'depot-teal-light': '#B0001F',
        'depot-amber': '#FFFFFF',
        'depot-brick': '#7A0019',
        'depot-moss': '#2E7D42',
      },
      fontFamily: {
        display: ['"Poppins"', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
};
