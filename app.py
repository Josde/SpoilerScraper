import asyncio
import datetime
import traceback
from datetime import datetime

from aiohttp import ClientSession
from sqlalchemy import orm
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
import re
import aiohttp
import nest_asyncio
import threading
from datetime import datetime
from wsgiref.handlers import format_date_time
from time import mktime

nest_asyncio.apply()
load_dotenv()
# TODO: Run flask migrations again due to change to VSCode // local idk
# TODO: Implement something like CacheControl to prevent many requests being made if the page is reloaded.
app = Flask(__name__)
# Make sure we're using postgresql:// rather than postgres:// due to SQLAlchemy deprecation.
app.config["SQLALCHEMY_DATABASE_URI"] = re.sub(r"^postgres:", "postgresql:", os.getenv("DATABASE_URL"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
db = SQLAlchemy(app)
migrate = Migrate(app, db)
from models import Chapter, MailingList
from form import MailForm
import mailing

_resultsWG = _resultsPK = _resultsTCB = _currentBreak = None
TIME_BETWEEN_UPDATES_MINS = 5
_last_modified_stamp = mktime(datetime.now().timetuple())


@app.before_first_request
def start_scraping_loop():
    t = threading.Thread(target=loop_in_thread, args=())
    t.start()


@app.after_request
def add_header(response):
    # fixes werkzeug > 0.9 etag error
    response.direct_passthrough = False
    response.cache_control.max_age = 300
    response.cache_control.public = True
    response.cache_control.must_revalidate = True
    response.headers["Last-Modified"] = format_date_time(_last_modified_stamp)
    response.add_etag()
    return response


@app.route("/", methods=["GET"])
async def index():
    while (
        _resultsWG is None or _resultsPK is None or _resultsTCB is None or _currentBreak is None
    ):  # I know I should implement a mutex here but I'm lazy.
        print("Waiting for parsing to be done.")
        await asyncio.sleep(0.5)
    spoilerNameWG, spoilerLinkWG, isActiveWG, errorWG = _resultsWG
    spoilerNamePK, spoilerLinkPK, isActivePK, errorPK = _resultsPK
    chapterNumber, chapterTitle, chapterLink, errorChapter = _resultsTCB
    currentBreak, breakError = _currentBreak, _breakError
    return render_template("index.html", **locals())


@app.route("/mail", methods=["GET", "POST"])
def mail():
    form = MailForm()
    print(request.method)
    if request.method == "GET":
        return render_template("mail.html", **locals())
    elif request.method == "POST":
        if form.validate_on_submit():
            email = request.form.get("email")
            dbEmail = MailingList.query.filter_by(mail=email).first()
            if dbEmail == None:
                dbEmail = MailingList(mail=email)
                db.session.add(dbEmail)
                db.session.commit()
                print("[Mail] Successfully created database entry for mail {0}".format(email))
                flash(
                    "The email address {0} has been signed up. Check your inbox to verify this address.".format(email)
                )
                mailing.sendVerificationMail(email, dbEmail.validation_key, deactivation=False)
            elif dbEmail != None and dbEmail.validated == True:
                flash(
                    "You have successfully requested deactivation for the account {0}. Check your inbox to complete this process.".format(
                        dbEmail.mail
                    )
                )
                print("[Mail] Successfully requested deactivation for mail {0}".format(email))
                mailing.sendVerificationMail(email, dbEmail.validation_key, deactivation=True)
            else:
                flash(
                    "It seems you have already tried to sign up with email {0}. We have resent you the validation link just in ccase.".format(
                        dbEmail.mail
                    )
                )
                print("[Mail] Successfully requested activation for mail {0}".format(email))
                mailing.sendVerificationMail(email, dbEmail.validation_key, deactivation=False)
        return redirect("/mail", code=303)


@app.route("/validate", methods=["GET"])
def validate():
    print(request.args)
    email = request.args.get("email")
    uuid = request.args.get("uuid")
    dbEmail = MailingList.query.filter_by(mail=email).first()
    if dbEmail == None:
        flash("There was an error while validating your sign up for {0}. Try again.".format(email))
        print("[Verification] Error activating mail {0}; user doesnt exist?".format(email))
    else:
        if dbEmail.validation_key == uuid:
            flash(
                "Signup successful for email {0}. You can unsubscribe anytime by checking the link at the bottom of emails.".format(
                    email
                )
            )
            dbEmail.validated = True
            db.session.commit()
            print("[Verification] Success activating {0}.".format(email))
        else:
            flash(
                "There was an error while validating your sign up for {0}. Try copying the link directly from the email.".format(
                    email
                )
            )
            print(
                "[Verification] Error activating {0}. UUID is {1} but should be {2}.".format(
                    email, uuid, dbEmail.validation_key
                )
            )
    return render_template("validate.html", **locals())


@app.route("/deactivate", methods=["GET"])
def deactivate():
    print(request.args)
    email = request.args.get("email")
    uuid = request.args.get("uuid")
    dbEmail = MailingList.query.filter_by(mail=email).first()
    if dbEmail == None:
        flash("There was an error while deactivating your sign up for {0}. Try again.".format(email))
        print("[Deactivation] Error deactivating mail {0}; user doesnt exist?".format(email))
    else:
        if dbEmail.validation_key == uuid:
            flash("Deactivation successful for email {0}.".format(email))
            dbEmail.validated = False
            db.session.commit()
            print("[Deactivation] Success deactivating {0}.".format(email))
        else:
            print(
                "[Deactivation] Error deactivating account {0}. UUID is {1} but should be {2}.".format(
                    email, uuid, dbEmail.validation_key
                )
            )
            flash(
                "There was an error while validating your sign up for {0}. Try copying the link directly from the email.".format(
                    email
                )
            )

    return render_template("validate.html", **locals())


async def scrapeWorstGen(asyncio_session: aiohttp.ClientSession):
    spoilerName = spoilerLink = error = ""
    isActive = None
    print("Scraping WorstGen")
    try:
        async with asyncio_session.get(
            "https://worstgen.alwaysdata.net/forum/forums/one-piece-spoilers.14/"
        ) as response:
            source = await response.text()
            soup = BeautifulSoup(source, "html.parser")
            for thread in soup.find_all("div", {"class": {"structItem-title"}}):
                threadTitle = thread.findChildren("a")[1]
                if "Summaries" in threadTitle.text:
                    spoilerName = threadTitle.text
                    spoilerLink = threadTitle["href"]
                    break
            # Scrape the thread and use post count to tell if spoilers are up (no replies will be made until spoilers are up, usually)
            currentThreadResponse = await asyncio_session.get(spoilerLink)
            currentThread = await currentThreadResponse.text()
            threadSoup = BeautifulSoup(currentThread, "html.parser")
            posts = threadSoup.find_all("div", {"class": {"message-cell message-cell--main"}})
            count = len(posts)
            if count > 1:
                isActive = True
            else:
                isActive = False
    except Exception:  # BeautifulSoup element not found
        print(traceback.format_exc())
        error = "Error parsing spoilers."
        return spoilerName, spoilerLink, isActive, error
    print("WorstGen done")
    return spoilerName, spoilerLink, isActive, error


async def scrapePirateKing(asyncio_session: aiohttp.ClientSession):
    print("Scraping Pirateking")
    spoilerName = spoilerLink = isActive = error = ""
    base_url = "https://pirate-king.es/foro"

    try:
        async with asyncio_session.get(base_url + "/viewforum.php?f=3") as response:
            source = await response.text()

            soup = BeautifulSoup(source, "html.parser")
            isActive = ""
            for thread in soup.find_all("a", {"class": "topictitle"}):
                if "Spoilers" in thread.text:
                    # Latest spoiler threads are always pinned; therefore the first thread with "spoilers" in title is the one for the current chapter.
                    spoilerLink = base_url + (thread["href"])[1:]  # TODO: this is a quickfix, clean this someday
                    spoilerName = thread.text
                    break
    except Exception:
        print(traceback.format_exc())
        error = "Error parsing spoilers."
        return spoilerName, spoilerLink, isActive, error
    # TODO: Figure out a way to parse if spoilers are up here. Since Redon is a moderator, the edit message doesn't show on his posts.
    print("Pirateking done")
    return spoilerName, spoilerLink, isActive, error


async def getChapter(asyncio_session: aiohttp.ClientSession):
    chapterNumber = chapterTitle = chapterLink = error = ""
    print("Scraping TCB")
    try:
        async with asyncio_session.get("https://onepiecechapters.com/mangas/5/one-piece") as response:
            source = await response.text()
            # TODO: Redirect to M+ when chapter is released officially.
            soup = BeautifulSoup(source, "html.parser")
            # Latest chapter is always at the top, therefore first box is the latest chapter.
            chapter = soup.find("a", {"class": "block border border-border bg-card mb-3 p-3 rounded"})
            # IMPROVEMENT: I could use regex to split this, but this will work until we get to Chapter 10000, so whatever.
            chapterNumber = chapter.findChild("div", {"class": "text-lg font-bold"}).text
            chapterTitle = chapter.findChild("div", {"class": "text-gray-500"}).text
            chapterLink = "https://onepiecechapters.com" + chapter["href"]
    except Exception:
        print(traceback.format_exc())
        error = "Error parsing chapter."
        return chapterNumber, chapterTitle, chapterLink, error
    print("TCB Done")
    return chapterNumber, chapterTitle, chapterLink, error


async def scrapeBreak(chapterNumber, asyncio_session: ClientSession):
    # Break data from ClayStage
    breakType = error = ""
    print("Scraping break")
    try:
        async with asyncio_session.get(
            "https://claystage.com/one-piece-chapter-release-schedule-for-2022"
        ) as response:
            source = await response.text()
            soup = BeautifulSoup(source, "html.parser")
            table = soup.find("table")
            table_body = table.find("tbody")
    except Exception:
        print(traceback.format_exc())
        error = "Error"
        return breakType, error

    breakType = "After Chapter {0}, there is ".format(chapterNumber)

    currentRow = -1
    rows = table_body.find_all("tr")
    for i in range(0, len(rows)):
        row = rows[i]
        cols = row.find_all("td")
        cols = [ele.text.strip() for ele in cols]
        if cols[1] == chapterNumber:
            currentRow = i
        if currentRow != -1 and (i == currentRow + 1 or i == currentRow + 2):
            text = cols[1]
            if "Break" not in text:
                text = "Chapter {0}".format(text)
            if i == currentRow + 1:
                breakType += text
            else:
                breakType += " and then {0}".format(text)

    print("Break done")
    return breakType, error


async def scrape_task():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
    }
    timeout = aiohttp.ClientTimeout(total=10)
    # TODO: Migrate all functions to async and aiohttp
    loop = asyncio.get_event_loop()

    global _resultsWG, _resultsPK, _resultsTCB, _currentBreak, _breakError, _last_modified_stamp
    while True:
        print("[{0}] Starting scraping".format(datetime.now()))
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            try:
                tasks = [scrapeWorstGen(session), scrapePirateKing(session), getChapter(session)]
                _resultsWG, _resultsPK, _resultsTCB = loop.run_until_complete(asyncio.gather(*tasks))
                chapterNumber, chapterTitle, chapterLink, errorChapter = _resultsTCB
            except Exception:
                traceback.print_exc()
            if errorChapter != "":
                _breakError = "Error parsing break."
            else:
                # TODO: Add error handling for the chapter number
                chapterNumberInt = int(chapterNumber[18:22]) if chapterNumber[18:22].isdigit() else None
                if chapterNumberInt != None:
                    dbChapter = Chapter.query.filter_by(id=1).first()
                    if dbChapter != None:
                        if dbChapter.number != chapterNumberInt:
                            dbChapter.number = chapterNumberInt
                            db.session.commit()
                            emailResults = MailingList.query.filter_by(validated=True).all()
                            recipients = []
                            for obj in emailResults:
                                recipients.append(obj.mail)
                            mailing.sendChapterMail(recipients, chapterNumber, chapterLink)
                    else:
                        dbChapter = Chapter(1, chapterNumber=chapterNumberInt, url=chapterLink)
                        db.session.add(dbChapter)
                        db.session.commit()
                async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                    try:
                        _currentBreak, _breakError = await scrapeBreak(str(chapterNumberInt), session)
                    except Exception:
                        traceback.print_exc()
        _last_modified_stamp = mktime(datetime.now().timetuple())
        await asyncio.sleep(TIME_BETWEEN_UPDATES_MINS * 60)


def loop_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(scrape_task())


# THIS RUNS ON STARTUP, IT IS ONLY DOWN HERE DUE TO NAMING ERRORS!!!
# FIXME: Hacky af, refactor this

if __name__ == "__main__":
    app.run()
