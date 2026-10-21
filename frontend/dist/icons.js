const paths={
overview:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
explore:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM16 8l-3 5-5 3 3-5 5-3Z',
analytics:'M4 20V10M12 20V4M20 20v-7',
review:'m8 12 3 3 5-6M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-3M8 2h8v4H8z',
source:'m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5',
settings:'M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8ZM10 2h4l1 3 3 1 3-1 2 4-2 2v3l2 2-2 4-3-1-3 1-1 3h-4l-1-3-3-1-3 1-2-4 2-2v-3L1 9l2-4 3 1 3-1 1-3Z',
arrow:'M5 12h14m-5-5 5 5-5 5',
diagonal:'M5 19 19 5M5 5h14v14',
down:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',
refresh:'M20 7V2m0 5h-5M4 17v5m0-5h5M20 7a9 9 0 0 0-15-3M4 17a9 9 0 0 0 15 3',
rain:'M7 14a4 4 0 1 1 0-8 5 5 0 0 1 9-1 4.5 4.5 0 1 1 2 9M8 17l-1 4m6-4-1 4m6-4-1 4',
sun:'M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2',
wind:'M3 8h12a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h6a3 3 0 1 1-3 3',
search:'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Zm-2 5 6 6',
logo:'M2 8c4-7 9 7 14 0l4-5M2 14c4-7 9 7 14 0l4-5M2 20c4-7 9 7 14 0l4-5'
};
export function icon(name){return `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name]||paths.arrow}"/></svg>`;}
