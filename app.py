from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
import re
app = Flask(__name__)


@app.route('/')
def index():
    sourceChapters = requests.get('https://onepiecechapters.com/one-piece/').text
    soupChapters = BeautifulSoup(sourceChapters, 'html.parser')
    # Latest chapter is always at the top, therefore first box is the latest chapter.
    chapter = soupChapters.find('div', {'class': 'elementor-image-box-content'}).text
    # TODO: I could use regex to split this, but this will work until we get to Chapter 10000, so whatever.
    chapterNumber = chapter[0:12]
    chapterTitle = chapter[12:]
    chapterLinkDiv = soupChapters.find('h5', {'class': 'elementor-image-box-title'}).findChildren('a')[0]
    chapterLink = chapterLinkDiv['href']

    sourceSpoilers = requests.get('https://www.pirate-king.es/foro/one-piece-manga-f3.html').text
    soupSpoilers = BeautifulSoup(sourceSpoilers, 'html.parser')
    for thread in soupSpoilers.find_all('a', {'class': 'topictitle'}):
        if "Spoilers" in thread.text:
            # Latest spoiler threads are always pinned; therefore the first thread with "spoilers" in title is the one for the current chapter.
            spoilersLink = thread['href']
            spoilersName = thread.text
            break;

    sourceSpoilersEng = requests.get('https://worstgen.alwaysdata.net/forum/forums/one-piece-spoilers.14/').text
    soupSpoilersEng = BeautifulSoup(sourceSpoilersEng, 'html.parser')
    for thread in soupSpoilersEng.find_all('div', {'class': {'structItem-title'}}):
        threadTitle = thread.findChildren('a')[1]
        if "Summaries" in threadTitle.text:
            spoilersNameEng = threadTitle.text
            spoilersLinkEng = threadTitle['href']
            break;
    return render_template('index.html', **locals())


if __name__ == '__main__':
    app.run()
