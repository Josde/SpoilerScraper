from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
import re
app = Flask(__name__)


@app.route('/')
def index():
    sourceChapters = requests.get('https://onepiecechapters.com/one-piece/').text
    soupChapters = BeautifulSoup(sourceChapters, 'html.parser')
    chapter = soupChapters.find('div', {'class': 'elementor-image-box-content'}).text
    chapterNumber = chapter[0:12]
    chapterTitle = chapter[12:]
    chapterLinkDiv = soupChapters.find('h5', {'class': 'elementor-image-box-title'}).findChildren('a')[0]
    chapterLink = chapterLinkDiv['href']

    sourceSpoilers = requests.get('https://www.pirate-king.es/foro/one-piece-manga-f3.html').text
    soupSpoilers = BeautifulSoup(sourceSpoilers, 'html.parser')
    for t in soupSpoilers.find_all('a', {'class': 'topictitle'}):
        if "Spoilers" in t.text:
            spoilersLink = t['href']
            spoilersName = t.text
            break;

    print(chapterLink)
    return render_template('index.html', **locals())


if __name__ == '__main__':
    app.run()
