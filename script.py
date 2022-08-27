import gspread
import telebot
import os
import schedule
import prettytable as pt
from oauth2client.service_account import ServiceAccountCredentials
from time import sleep
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from flask import Flask, request
from telegram import ParseMode
from threading import Thread

load_dotenv()
API_KEY = os.getenv('API_KEY')
CHAT_ID = os.getenv('chat_id')
GOOGLE_APP_CREDS = {
    "type": os.getenv("type"),
    "project_id": os.getenv("project_id"),
    "private_key_id": os.getenv("private_key_id"),
    "private_key": os.getenv("private_key"),
    "client_email": os.getenv("client_email"),
    "client_id": os.getenv("client_id"),
    "auth_uri": os.getenv("auth_uri"),
    "token_uri": os.getenv("token_uri"),
    "auth_provider_x509_cert_url": os.getenv("auth_provider_x509_cert_url"),
    "client_x509_cert_url": os.getenv("client_x509_cert_url")
}
GOOGLE_APP_CREDS['private_key'] = GOOGLE_APP_CREDS['private_key'].replace(
    '\\n', '\n')

bot = telebot.TeleBot(API_KEY)
server = Flask(__name__)

usernameMap = {
    os.getenv("abhishek_username"): "Abhishek",
    os.getenv("pradeep_username"): "Pradeep",
    os.getenv("priyan_username"): "Priyan",
    os.getenv("sukrut_username"): "Sukrut",
    os.getenv("shantanu_username"): "Shantanu",
}

nameMap = {
    "Abhishek": os.getenv("abhishek_username"),
    "Pradeep": os.getenv("pradeep_username"),
    "Priyan": os.getenv("priyan_username"),
    "Sukrut": os.getenv("sukrut_username"),
    "Shantanu": os.getenv("shantanu_username")
}

categories = {
    'run': 1,
    'cycle': 5,
    'walk': 3
}


class DateTime:
    def getDateObj(dateStr):
        return datetime.fromisoformat(dateStr)


class SheetDB():
    def __init__(self):
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            GOOGLE_APP_CREDS)
        client = gspread.authorize(creds)
        self.sheet = client.open("weekly_distance_log").get_worksheet(0)
        self.excess_sheet = client.open("weekly_distance_log").get_worksheet(1)

    def getAllRecords(self, sheet):
        data = sheet.get_all_records()
        return data

    def insertRecord(self, name, category, distance):
        curr_date = str(date.today())
        row = [curr_date, name, category, distance]
        self.sheet.insert_row(row, 2)
        print('Record Inserted!')

    def deleteMultipleRecords(self, indexes):
        for i in indexes[::-1]:
            self.sheet.delete_rows(i+2)
        print('Records Deleted!')

    def filterRecords(self, weekly_status=True):
        data = self.getAllRecords(self.sheet)
        if weekly_status:
            currDate = str(date.today())
            timestampDate = DateTime.getDateObj(currDate)
            lastMonday = timestampDate - \
                timedelta(days=timestampDate.weekday())
            filtered = list(
                filter(lambda x: DateTime.getDateObj(x['Date']) >= lastMonday, data))
            data = filtered
        return data

    def getDistanceStats(self, weekly_status=True):
        records = self.filterRecords(weekly_status)
        progressMap = {}
        for name in usernameMap.values():
            progressMap[name] = {}
            for category in categories.keys():
                progressMap[name][category] = 0
            curr_records = list(filter(lambda x: x['Name'] == name, records))
            for record in curr_records:
                category = record['Category']
                progressMap[name][category] += record['Distance']
        return progressMap

    def getLastWeeklyIndexByName(self, name):
        data = self.getAllRecords(self.sheet)
        currDate = str(date.today())
        timestampDate = DateTime.getDateObj(currDate)
        lastMonday = timestampDate - timedelta(days=timestampDate.weekday())
        for i, x in enumerate(data):
            if x['Name'] == name and DateTime.getDateObj(x['Date']) >= lastMonday:
                return i
        return -1

    def getWeeklyExcessStats(self):
        records = self.getAllRecords(self.excess_sheet)
        excessMap = {}
        for i in records:
            excessMap[i['Name']] = i['Excess']
        return excessMap

    def getDistanceStatsReply(self, progressMap, weekly_status):
        table = pt.PrettyTable()
        table.title = "All Time Distance Stats"
        if weekly_status:
            table.title = "Weekly Distance Stats"
        table.field_names = (['', 'Run', 'Cycl', 'Walk'])
        table.align[''] = 'l'
        table.align['Run'] = 'r'
        table.align['Cycl'] = 'r'
        table.align['Walk'] = 'r'
        sortedProgressMap = {k: v for k, v in sorted(
            progressMap.items(), key=lambda item: -(item[1]['run']/categories['run'] + item[1]['cycle']/categories['cycle'] + item[1]['walk']/categories['walk']))}
        for name in sortedProgressMap:
            row = [name[0:3]]
            for category in categories.keys():
                value = progressMap[name][category]
                row.append(f'{value:.2f}')
            table.add_row(row)
        print(table)
        return table

    def roundDown(self, progressMap):
        for i in progressMap:
            if progressMap[i] > 10:
                progressMap[i] = 10
        return progressMap


def sendProgressReply(message, progressMap, weekly_status=True):
    progressReply = sheetdb.getDistanceStatsReply(progressMap, weekly_status)
    bot.send_message(
        message.chat.id, f'<pre>{progressReply}</pre>', parse_mode=ParseMode.HTML)

# -----------------------------------------------


@bot.message_handler(commands=['all_time_stats'])
def progress(message):
    progressMap = sheetdb.getDistanceStats(weekly_status=False)
    sendProgressReply(message, progressMap, weekly_status=False)

# -----------------------------------------------


@bot.message_handler(commands=['weekly_stats'])
def progressWeekly(message):
    progressMap = sheetdb.getDistanceStats()
    sendProgressReply(message, progressMap)

# -----------------------------------------------


def distance_request(message):
    invalid_commands = []
    for category in categories.keys():
        invalid_commands.append("/" + category)
        invalid_commands.append(
            "/" + category + "@weekly_distance_tracker_bot")

    if message.text:
        if message.text in invalid_commands:
            bot.send_message(
                message.chat.id, "Enter distance following /<category>.\nFor e.g. /run 4.5")
            return False
        request = message.text.split()
        if len(request) >= 2 and request[0][1:] in categories.keys() and request[1].replace('.', '', 1).isdigit() and float(request[1]) > 0:
            print("Valid distance update request!")
            return True
    return False


def computeScaledDistance(name, progressMap):
    currTotal = 0
    for category, ratio in categories.items():
        currTotal += progressMap[name][category]/ratio
    return currTotal


@bot.message_handler(func=distance_request)
def distanceReply(message):
    name = usernameMap[message.from_user.username]
    bot.send_message(message.chat.id, "Nice one {} ! 💪".format(name))
    category, distance = message.text[1:].split()

    prevProgressMap = sheetdb.getDistanceStats()
    prevWeeklyExcessStatusAboveLimit = True if computeScaledDistance(
        name, prevProgressMap) >= 10 else False

    sheetdb.insertRecord(name, category, distance)

    currProgressMap = sheetdb.getDistanceStats()
    if computeScaledDistance(name, currProgressMap) >= 10 and not prevWeeklyExcessStatusAboveLimit:
        bot.send_message(
            message.chat.id, "Congrats on achieving your weekly target {} !!! 🥳".format(name))

    sendProgressReply(message, currProgressMap)

# -----------------------------------------------


@bot.message_handler(commands=['delete'])
def deletePrevEntry(message):
    name = usernameMap[message.from_user.username]
    bot.send_message(
        message.chat.id, "🚧 Deleting your last activity {}...".format(name))
    deleteIndex = sheetdb.getLastWeeklyIndexByName(name)
    if deleteIndex != -1:
        sheetdb.deleteMultipleRecords([deleteIndex])
        progressWeekly(message)
    else:
        bot.send_message(
            message.chat.id, "You haven't logged any activities in the past week! 😭".format(name))

# -----------------------------------------------


def schedule_checker():
    while True:
        schedule.run_pending()
        sleep(1)


def saturday_reminder():
    progressMap = sheetdb.getDistanceStats()
    inactive_members = []
    for name in progressMap:
        active_status = False
        for category in categories.keys():
            active_status = active_status or progressMap[name][category] > 0
        if not active_status:
            inactive_members.append("@"+nameMap[name])
    if len(inactive_members) > 0:
        bot.send_message(CHAT_ID, ' '.join(inactive_members) +
                         " It's almost the end of the week ! Try to log an activity before the weekly challenge ends !!!")
    print("Saturday reminder complete!")


def send_progress():
    bot.send_message(
        CHAT_ID, "Great going guys ! Cheers to the end of another week of this challenge ! 🍻")
    progressMap = sheetdb.getDistanceStats(weekly_status=False)
    progressReply = sheetdb.getDistanceStatsReply(
        progressMap, weekly_status=False)
    bot.send_message(
        CHAT_ID, f'<pre>{progressReply}</pre>', parse_mode=ParseMode.HTML)
    print("Weekly all-time progress sent!")

# -----------------------------------------------


@bot.message_handler(commands=['chat_id'])
def chat_id(message):
    bot.send_message(
        message.chat.id, "Chat ID: "+str(message.chat.id))


@server.route('/' + API_KEY, methods=['POST'])
def getMessage():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(
        url='https://weekly-distance-tracker-bot.herokuapp.com/' + API_KEY)
    return "!", 200


if __name__ == "__main__":
    schedule.every().saturday.at("02:00").do(saturday_reminder)
    schedule.every().sunday.at("14:30").do(send_progress)
    Thread(target=schedule_checker).start()

    sheetdb = SheetDB()
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
