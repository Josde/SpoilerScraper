from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
from requests_html import HTMLSession
from datetime import *
import re
import requests_cache
import redis
#TODO: Implement something like CacheControl to prevent many requests being made if the page is reloaded.
pool = redis.ConnectionPool(host=REDIS_URL, port=6379, db=0)
requests_cache.install_cache(backend='redis', expire_after=300, connection_pool=pool)
app = Flask(__name__)





@app.route('/')
def index():
    spoilerNameWG, spoilerLinkWG, isActiveWG = scrapeWorstGen()
    spoilerNamePK, spoilerLinkPK, isActivePK = scrapePirateKing()
    chapterNumber, chapterTitle, chapterLink = getChapter()
    currentBreak = scrapeBreak(chapterNumber[8:])
    return render_template('index.html', **locals())


if __name__ == '__main__':
    app.run()

def scrapeWorstGen():
    source = requests.get('https://worstgen.alwaysdata.net/forum/forums/one-piece-spoilers.14/').text
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
    count = 0
    for post in threadSoup.find_all('div', {'class': {'message-cell message-cell--main'}}):
        count += 1
    if count > 1:
        if count < 20:
            isActive = "(ACTIVE, {0} POSTS)".format(count)
        else:
            #TODO: If thread has more than 20 posts, we should recursively parse the next pages to get all posts. Too lazy for that rn.
            isActive = "(ACTIVE, {0}+ POSTS)".format(count)
    else:
        isActive = "(INACTIVE)"
    return spoilerName, spoilerLink, isActive

def scrapePirateKing():
    source = requests.get('https://www.pirate-king.es/foro/one-piece-manga-f3.html').text
    soup = BeautifulSoup(source, 'html.parser')
    isActive = ""
    for thread in soup.find_all('a', {'class': 'topictitle'}):
        if "Spoilers" in thread.text:
            # Latest spoiler threads are always pinned; therefore the first thread with "spoilers" in title is the one for the current chapter.
            spoilerLink = thread['href']
            spoilerName = thread.text
            break;
    #TODO: Figure out a way to parse if spoilers are up here. Since Redon is a moderator, the edit message doesn't show on his posts.
    return spoilerName, spoilerLink, isActive

def getChapter():
    #TODO: Redirect to M+ when chapter is released officially.
    source = requests.get('https://onepiecechapters.com/one-piece/').text
    soup = BeautifulSoup(source, 'html.parser')
    # Latest chapter is always at the top, therefore first box is the latest chapter.
    chapter = soup.find('div', {'class': 'elementor-image-box-content'}).text
    # IMPROVEMENT: I could use regex to split this, but this will work until we get to Chapter 10000, so whatever.
    chapterNumber = chapter[0:12]
    chapterTitle = chapter[12:]
    chapterLinkDiv = soup.find('h5', {'class': 'elementor-image-box-title'}).findChildren('a')[0]
    chapterLink = chapterLinkDiv['href']
    return chapterNumber, chapterTitle, chapterLink

def scrapeBreak(chapterNumber):
    # Break data from ClayStage
    header = {'User-Agent': 'Mozilla/5.0'}
    session = HTMLSession()
    source = session.get('https://claystage.com/one-piece-chapter-release-schedule-for-2021', headers=header).text
    soup = BeautifulSoup(source, 'html.parser')
    table = soup.find('table')
    table_body = table.find('tbody')
    breakType = ""
    isCurrentChapter = 0
    #currentRow = 0 currently unused
    for row in table_body.find_all('tr'):
        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        if isCurrentChapter:
            breakType = cols[1]
            break;
        if isCurrentChapter == 0 and cols[1] == chapterNumber:
            isCurrentChapter = 1

    if "Break" not in breakType:
        breakType = "NO BREAK NEXT WEEK"
    return breakType