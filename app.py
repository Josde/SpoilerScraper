import traceback

import requests
import requests_cache
from bs4 import BeautifulSoup
from flask import Flask, render_template
from requests_html import HTMLSession
from flask_caching import Cache
#TODO: Implement something like CacheControl to prevent many requests being made if the page is reloaded.
requests_cache.install_cache(backend='memory', expire_after=300)
cache = Cache(config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})
app = Flask(__name__)
cache.init_app(app)



@app.route('/')
@cache.cached(timeout=300)
def index():
    spoilerNameWG, spoilerLinkWG, isActiveWG = scrapeWorstGen()
    spoilerNamePK, spoilerLinkPK, isActivePK = scrapePirateKing()
    chapterNumber, chapterTitle, chapterLink = getChapter()
    if (chapterNumber == "Error parsing chapter."):
        currentBreak = "Error parsing break."
    else:
        currentBreak = scrapeBreak(chapterNumber[18:22])
    return render_template('index.html', **locals())


if __name__ == '__main__':
    app.run()

def scrapeWorstGen():
    try:
        source = requests.get('https://worstgen.alwaysdata.net/forum/forums/one-piece-spoilers.14/', timeout=5.000).text
    except requests.exceptions.Timeout:
        print(traceback.format_exc())
        return "Site down.", "", ""
    try:
        soup = BeautifulSoup(source, 'html.parser')
        for thread in soup.find_all('div', {'class': {'structItem-title'}}):
            threadTitle = thread.findChildren('a')[1]
            if "Summaries" in threadTitle.text:
                spoilerName = threadTitle.text
                spoilerLink = threadTitle['href']
                break;
        # Scrape the thread and use post count to tell if spoilers are up (no replies will be made until spoilers are up, usually)
        currentThread = requests.get(spoilerLink).text
        threadSoup = BeautifulSoup(currentThread, 'html.parser')
        posts = threadSoup.find_all('div', {'class': {'message-cell message-cell--main'}})
        count = len(posts)
        if count > 1:
            if count < 20:
                isActive = "(ACTIVE, {0} POSTS)".format(count)
            else:
                #TODO: If thread has more than 20 posts, we should recursively parse the next pages to get all posts. Too lazy for that rn.
                isActive = "(ACTIVE, {0}+ POSTS)".format(count)
        else:
            isActive = "(INACTIVE)"
    except AttributeError: #BeautifulSoup element not found
        print(traceback.format_exc())
        return "Error parsing spoilers.", "", ""
    return spoilerName, spoilerLink, isActive

def scrapePirateKing():
    try:
        source = requests.get('https://www.pirate-king.es/foro/one-piece-manga-f3.html', timeout=5.000).text
    except requests.exceptions.Timeout:
        print(traceback.format_exc())
        return "Site down.", "", ""
    try:
        soup = BeautifulSoup(source, 'html.parser')
        isActive = ""
        for thread in soup.find_all('a', {'class': 'topictitle'}):
            if "Spoilers" in thread.text:
                # Latest spoiler threads are always pinned; therefore the first thread with "spoilers" in title is the one for the current chapter.
                spoilerLink = thread['href']
                spoilerName = thread.text
                break;
    except AttributeError:
        print(traceback.format_exc())
        return "Error parsing spoilers.", "", ""
    #TODO: Figure out a way to parse if spoilers are up here. Since Redon is a moderator, the edit message doesn't show on his posts.
    return spoilerName, spoilerLink, isActive

def getChapter():
    #TODO: Redirect to M+ when chapter is released officially.
    try:
        source = requests.get('https://onepiecechapters.com/mangas/5/one-piece', timeout=5.000).text
    except requests.exceptions.Timeout:
        return "Site down.", "", ""
    try:
        soup = BeautifulSoup(source, 'html.parser')
        # Latest chapter is always at the top, therefore first box is the latest chapter.
        chapter = soup.find('a', {'class': 'block border border-border bg-card mb-3 p-3 rounded'})
        # IMPROVEMENT: I could use regex to split this, but this will work until we get to Chapter 10000, so whatever.
        chapterNumber = chapter.findChild('div', {'class': 'text-lg font-bold'}).text
        chapterTitle = chapter.findChild('div', {'class': 'text-gray-500'}).text
        chapterLink = "https://onepiecechapters.com" + chapter['href']
    except AttributeError:
        print(traceback.format_exc())
        return "Error parsing chapter.", "", ""
    return chapterNumber, chapterTitle, chapterLink

def scrapeBreak(chapterNumber):
    # Break data from ClayStage
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36'}
    session = HTMLSession()
    source = session.get('https://claystage.com/one-piece-chapter-release-schedule-for-2021', headers=header).text
    soup = BeautifulSoup(source, 'html.parser')
    try:
        table = soup.find('table')
        table_body = table.find('tbody')
    except Exception:
        print(traceback.format_exc())
        print(soup)
        breakType = "There was an error parsing break data."
        return breakType

    breakType = "After Chapter {0}, there is ".format(chapterNumber)

    currentRow = -1
    rows = table_body.find_all('tr')
    for i in range (0, len(rows)):
        row = rows[i]
        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        if cols[1] == chapterNumber:
            currentRow = i
        if currentRow != -1 and (i == currentRow+1 or i == currentRow+2):
            text = cols[1]
            if "Break" not in text:
                text = "Chapter {0}".format(text)
            if (i == currentRow+1):
                breakType += text
            else:
                breakType += " and then {0}".format(text)


    return breakType