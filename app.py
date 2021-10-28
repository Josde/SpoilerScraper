import traceback

import requests
import requests_cache
from sqlalchemy import orm
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, flash
from requests_html import HTMLSession
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
import re
load_dotenv()
#TODO: Implement something like CacheControl to prevent many requests being made if the page is reloaded.
requests_cache.install_cache(backend='memory', expire_after=300)
cache = Cache(config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300})
app = Flask(__name__)
cache.init_app(app)
#Make sure we're using postgresql:// rather than postgres:// due to SQLAlchemy deprecation.
app.config['SQLALCHEMY_DATABASE_URI'] = re.sub(r'^postgres:', 'postgresql:', os.getenv('DATABASE_URL'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db = SQLAlchemy(app)
migrate = Migrate(app, db)


from models import Chapter, MailingList
from form import MailForm
import mailing

@app.route('/', methods=['GET'])
@cache.cached(timeout=300)
def index():
    #TODO: Split this into 2 pages to make caching work again.
    spoilerNameWG, spoilerLinkWG, isActiveWG, errorWG = scrapeWorstGen()
    spoilerNamePK, spoilerLinkPK, isActivePK, errorPK = scrapePirateKing()
    chapterNumber, chapterTitle, chapterLink, errorChapter = getChapter()

    if (errorChapter != ""):
        currentBreak = "Error parsing break."
    else:
        # TODO: Add error handling for the chapter number
        chapterNumberInt = int(chapterNumber[18:22]) if chapterNumber[18:22].isdigit() else None
        if chapterNumberInt != None:
            try:
                dbChapter = Chapter.query.filter_by(id=1).first()
                if (dbChapter.number != chapterNumberInt):
                    dbChapter.chapterNumber = chapterNumberInt
                    db.session.commit()
                    emailResults = MailingList.query.filter_by(validated=True).all()
                    recipients = []
                    for obj in emailResults:
                        recipients.append(obj.mail)
                    mailing.sendChapterMail(recipients, chapterNumber, chapterLink)
            except orm.exc.NoResultFound:
                dbChapter = Chapter(1, chapterNumber=chapterNumberInt, url=chapterLink)
                db.session.add(dbChapter)
                db.session.commit()
        currentBreak = scrapeBreak(str(chapterNumberInt))
    return render_template('index.html', **locals())

@app.route('/mail', methods=['GET', 'POST'])
def mail():
    form = MailForm()
    print(request.method)
    if request.method == 'GET':
        return render_template('mail.html', **locals())
    elif request.method == 'POST':
        if form.validate_on_submit():
            email = request.form.get('email')
            dbEmail = MailingList.query.filter_by(mail=email).first()
            if (dbEmail == None):
                dbEmail = MailingList(mail=email)
                db.session.add(dbEmail)
                db.session.commit()
                print('[Mail] Successfully created database entry for mail {0}'.format(email))
                flash('The email address {0} has been signed up. Check your inbox to verify this address.'.format(email))
                mailing.sendVerificationMail(email, dbEmail.validation_key, deactivation=False)
            elif (dbEmail != None and dbEmail.validated == True):
                flash('You have successfully requested deactivation for the account {0}. Check your inbox to complete this process.'.format(dbEmail.mail))
                print('[Mail] Successfully requested deactivation for mail {0}'.format(email))
                mailing.sendVerificationMail(email, dbEmail.validation_key, deactivation=True)
            else:
                flash('It seems you have already tried to sign up with email {0}. We have resent you the validation link just in ccase.'.format(dbEmail.mail))
                print('[Mail] Successfully requested activation for mail {0}'.format(email))
                mailing.sendVerificationMail(email, dbEmail.validation_key, deactivation=False)
        return redirect('/mail', code=303)

@app.route('/validate', methods=['GET'])
def validate():
    print(request.args)
    email = request.args.get('email')
    uuid = request.args.get('uuid')
    dbEmail = MailingList.query.filter_by(mail=email).first()
    if (dbEmail == None):
        flash('There was an error while validating your sign up for {0}. Try again.'.format(email))
        print('[Verification] Error activating mail {0}; user doesnt exist?'.format(email))
    else:
        if (dbEmail.validation_key == uuid):
            flash('Signup successful for email {0}. You can unsubscribe anytime by checking the link at the bottom of emails.'.format(email))
            dbEmail.validated = True
            db.session.commit()
            print('[Verification] Success activating {0}.'.format(email))
        else:
            flash('There was an error while validating your sign up for {0}. Try copying the link directly from the email.'.format(email))
            print('[Verification] Error activating {0}. UUID is {1} but should be {2}.'.format(email, uuid, dbEmail.validation_key))
    return render_template('validate.html', **locals())

@app.route('/deactivate', methods=['GET'])
def deactivate():
    print(request.args)
    email = request.args.get('email')
    uuid = request.args.get('uuid')
    dbEmail = MailingList.query.filter_by(mail=email).first()
    if (dbEmail == None):
        flash('There was an error while deactivating your sign up for {0}. Try again.'.format(email))
        print('[Deactivation] Error deactivating mail {0}; user doesnt exist?'.format(email))
    else:
        if (dbEmail.validation_key == uuid):
            flash('Deactivation successful for email {0}.'.format(email))
            dbEmail.validated = False
            db.session.commit()
            print('[Deactivation] Success deactivating {0}.'.format(email))
        else:
            print('[Deactivation] Error deactivating account {0}. UUID is {1} but should be {2}.'.format(email, uuid, dbEmail.validation_key))
            flash('There was an error while validating your sign up for {0}. Try copying the link directly from the email.'.format(email))

    return render_template('validate.html', **locals())
if __name__ == '__main__':
    app.run()

def scrapeWorstGen():
    spoilerName = spoilerLink = isActive = error = ""
    try:
        source = requests.get('https://worstgen.alwaysdata.net/forum/forums/one-piece-spoilers.14/', timeout=5.000).text
    except requests.exceptions.Timeout:
        print(traceback.format_exc())
        error = "Site down."
        return spoilerName, spoilerLink, isActive, error
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
        error = "Error parsing spoilers."
        return spoilerName, spoilerLink, isActive, error
    return spoilerName, spoilerLink, isActive, error

def scrapePirateKing():
    spoilerName = spoilerLink = isActive = error = ""
    try:
        source = requests.get('https://www.pirate-king.es/foro/one-piece-manga-f3.html', timeout=5.000).text
    except requests.exceptions.Timeout:
        print(traceback.format_exc())
        error = "Site down."
        return spoilerName, spoilerLink, isActive, error
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
        error = "Error parsing spoilers."
        return spoilerName, spoilerLink, isActive, error
    #TODO: Figure out a way to parse if spoilers are up here. Since Redon is a moderator, the edit message doesn't show on his posts.
    return spoilerName, spoilerLink, isActive, error

def getChapter():
    chapterNumber = chapterTitle = chapterLink = error = ""
    #TODO: Redirect to M+ when chapter is released officially.
    try:
        source = requests.get('https://onepiecechapters.com/mangas/5/one-piece', timeout=5.000).text
    except requests.exceptions.Timeout:
        error = "Site down."
        return chapterNumber, chapterTitle, chapterLink, error
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
        error = "Error parsing chapter."
        return chapterNumber, chapterTitle, chapterLink, error
    return chapterNumber, chapterTitle, chapterLink, error

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