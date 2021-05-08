import gspread
import telebot
import os
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from time import time, strptime
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()
API_KEY = os.getenv('API_KEY')
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
GOOGLE_APP_CREDS['private_key'] = GOOGLE_APP_CREDS['private_key'].replace('\\n', '\n')

bot = telebot.TeleBot(API_KEY)
server = Flask(__name__)

EXCESS_FACTOR = 4
names = ["Abhishek", "Pradeep", "Priyan", "Sukrut"]
excessDistanceMap = {
    "Abhishek": [2,2],
    "Pradeep": [3,2],
    "Priyan": [4,2],
    "Sukrut": [5,2]
}

class DateTime:
    def getDateObj(dateStr):
        return datetime.fromisoformat(dateStr) 

class SheetDB():
    def __init__(self):
        scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_APP_CREDS)
        client = gspread.authorize(creds)
        self.sheet = client.open("weekly_distance_log").get_worksheet(0)
        self.excess_sheet = client.open("weekly_distance_log").get_worksheet(1)
    
    def getAllRecords(self, sheet):
        data = sheet.get_all_records()
        return data

    def insertRecord(self, name, distance):
        curr_date = str(date.today())
        row = [curr_date, name, distance]
        self.sheet.insert_row(row, 2)
        print('Record Inserted!')

    def updateExcess(self, name, excess):
        global excessDistanceMap
        row = excessDistanceMap[name][0]
        col = excessDistanceMap[name][1]
        curr_value = self.excess_sheet.cell(row,col).value
        updated_value = round(float(curr_value)+excess,2)
        self.excess_sheet.update_cell(row,col,updated_value)
        print('Excess Updated!')

    def changeExcess(self, name, excess):
        global excessDistanceMap
        row = excessDistanceMap[name][0]
        col = excessDistanceMap[name][1]
        self.excess_sheet.update_cell(row,col,excess)
        print('Excess Changed!')

    def deleteLastRecord(self):
        self.sheet.delete_row(2)
        print('Record Deleted!')

    def deleteMultipleRecords(self, indexes):
        for i in indexes[::-1]:
            self.sheet.delete_row(i+2)
        print ('Records Deleted!')

    def filterWeeklyRecords(self):
        data = self.getAllRecords(self.sheet)
        currDate = str(date.today())
        timestampDate = DateTime.getDateObj(currDate)
        lastMonday = timestampDate - timedelta(days=timestampDate.weekday())
        filtered =  list(filter(lambda x: DateTime.getDateObj(x['Date']) >= lastMonday, data))
        return filtered

    def getWeeklyIndexesByName(self, name):
        data = self.getAllRecords(self.sheet)
        currDate = str(date.today())
        timestampDate = DateTime.getDateObj(currDate)
        lastMonday = timestampDate - timedelta(days=timestampDate.weekday())
        indexArr = []
        for i, x in enumerate(data):
            if x['Name'] == name and DateTime.getDateObj(x['Date']) >= lastMonday:
                indexArr.append(i)
        return indexArr
    
    def getWeeklyStats(self):
        records = self.filterWeeklyRecords()
        progressMap = {}
        for name in names:
            progressMap[name] = 0
            curr_records = list(filter(lambda x: x['Name'] == name, records))
            for record in curr_records:
                progressMap[name] += record['Distance']
        return progressMap
    
    def getWeeklyExcessStats(self):
        records = self.getAllRecords(self.excess_sheet)
        excessMap = {}
        for i in records:
            excessMap[i['Name']] = i['Excess']
        return excessMap
    
    def getWeeklyStatsReply(self, progressMap, excessMap):
        progressReply = "***Weekly Progress***\n"
        for name in progressMap:
            progressReply += (f"    {name} : {round(progressMap[name],2)}/{excessMap[name]}\n")
        print (progressReply)
        return progressReply

    def roundDown(self,progressMap):
        for i in progressMap:
            if progressMap[i] > 10: progressMap[i] = 10
        return progressMap
    
@bot.message_handler(commands=['progress'])
def progress(message):
    progressMap = sheetdb.roundDown(sheetdb.getWeeklyStats())
    excessMap = sheetdb.getWeeklyExcessStats()
    progressReply = sheetdb.getWeeklyStatsReply(progressMap, excessMap)
    bot.send_message(message.chat.id, progressReply)

def distance_request(message):
    if message.text:
        if message.text in ["/log","/log@weekly_distance_tracker_bot"]:
            bot.send_message(message.chat.id, "Enter distance followed by /log.\nFor e.g. /log 4.5")
            return False
        request = message.text.split()
        if len(request)>=2 and request[0] == "/log" and request[1].replace('.','',1).isdigit() and float(request[1])>0:
            print('Valid distance update request!')
            return True
    return False

@bot.message_handler(func=distance_request)
def distanceReply(message):
    name = message.from_user.first_name
    bot.send_message(message.chat.id, "Nice one {} ! 💪".format(name))
    distance = message.text.split()[1]
    prevProgressMap = sheetdb.getWeeklyStats()
    prevWeeklyExcessStatusAboveLimit = True if prevProgressMap[name] >= 10 else False
    
    sheetdb.insertRecord(name,distance)
    
    currProgressMap = sheetdb.getWeeklyStats()

    currExcess = 0
    if currProgressMap[name] > 10:
        if prevWeeklyExcessStatusAboveLimit:
            currExcess = currProgressMap[name] - prevProgressMap[name]
        else: 
            currExcess = currProgressMap[name] - 10
            bot.send_message(message.chat.id, "Congrats on achieving your weekly target {} !!! 🥳".format(name))
        currProgressMap[name] = 10

    if currExcess>0:
        sheetdb.updateExcess(name,currExcess)

    excessMap = sheetdb.getWeeklyExcessStats()
    progressReply = sheetdb.getWeeklyStatsReply(currProgressMap, excessMap)
    
    bot.send_message(message.chat.id, progressReply)

def excess_request(message):
    if message.text and message.text == "/redeem":
        print('Valid redeem request!')
        return True
    return False

@bot.message_handler(commands=['redeem'])
def distanceReply(message):
    name = message.from_user.first_name
    reply = "You have already reached your weekly target {} ! 😎".format(name)

    progressMap = sheetdb.getWeeklyStats()
    if progressMap[name] < 10:
        requiredDistance = 10-progressMap[name]
        scaledExcess = requiredDistance*EXCESS_FACTOR
        excessMap = sheetdb.getWeeklyExcessStats()
        if excessMap[name] < scaledExcess:
            reply = "You have not accumulated sufficient excess mileage {} ! 😭".format(name)
        else:
            sheetdb.insertRecord(name,requiredDistance)
            sheetdb.updateExcess(name,-1*scaledExcess)
            reply = "You have successfully redeemed your excess mileage {} ! 👌".format(name)

    bot.send_message(message.chat.id, reply)

    currProgressMap = sheetdb.roundDown(sheetdb.getWeeklyStats())
    excessMap = sheetdb.getWeeklyExcessStats()
    progressReply = sheetdb.getWeeklyStatsReply(currProgressMap, excessMap)
    bot.send_message(message.chat.id, progressReply)

def manual_request(message):
    if message.text:
        if message.text in ["/manual","/manual@weekly_distance_tracker_bot"]:
            bot.send_message(message.chat.id, "Enter weekly and excess mileage\nfollowed by /manual.\nFor e.g. /manual 9.5 13.2")
            return False
        request = message.text.split()
        if len(request)>=3 and request[0] == "/manual" and request[1].replace('.','',1).isdigit() and float(request[1])>0 and request[2].replace('.','',1).isdigit() and float(request[2])>0:
            print('Valid manual update request!')
            return True
    return False

@bot.message_handler(func=manual_request)
def manualReply(message):
    name = message.from_user.first_name
    bot.send_message(message.chat.id, '🚧 Manual update for {} in progress...'.format(name))

    # delete weekly records
    weeklyIndexes = sheetdb.getWeeklyIndexesByName(name)
    sheetdb.deleteMultipleRecords(weeklyIndexes)

    # insert new record and update excess
    req = message.text.split()
    distance = req[1]
    excess = float(req[2])
    if float(distance) > 0: sheetdb.insertRecord(name, distance)
    if excess > 0: sheetdb.changeExcess(name, excess)

    # return weekly progress
    progressMap = sheetdb.roundDown(sheetdb.getWeeklyStats())
    excessMap = sheetdb.getWeeklyExcessStats()
    progressReply = sheetdb.getWeeklyStatsReply(progressMap, excessMap)
    bot.send_message(message.chat.id, progressReply)    

@server.route('/' + API_KEY, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://weekly-distance-tracker-bot.herokuapp.com/' + API_KEY)
    return "!", 200

if __name__ == "__main__":
    sheetdb = SheetDB()
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))