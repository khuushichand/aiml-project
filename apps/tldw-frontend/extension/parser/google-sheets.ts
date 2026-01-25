import * as cheerio from 'cheerio';

export const parseGoogleSheets = (html: string) => {
  cheerio.load(html);
};
