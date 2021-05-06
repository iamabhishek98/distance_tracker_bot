import gspread
import telebot
import os
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from time import time, strptime
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('API_KEY')
bot = telebot.TeleBot(API_KEY)

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
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
        client = gspread.authorize(creds)
        self.sheet = client.open("weekly_distance_log").get_worksheet(0)
        self.excess_sheet = client.open("weekly_distance_log").get_worksheet(1)
        self.datetime = DateTime()
    
    def getAllRecords(self, sheet):
        data = sheet.get_all_records()
        # pprint(data)
        return data

    def insertRecord(self, name, distance):
        curr_date = str(date.today())
        row = [curr_date, name, distance]
        self.sheet.insert_row(row, 2)
        print('Record Inserted')

    def updateExcess(self, name, excess):
        global excessDistanceMap
        row = excessDistanceMap[name][0]
        col = excessDistanceMap[name][1]
        curr_value = self.excess_sheet.cell(row,col).value
        updated_value = round(float(curr_value)+excess,2)
        self.excess_sheet.update_cell(row,col,updated_value)
        print('Excess Updated')

    def deleteLastRecord(self):
        self.sheet.delete_rows(2)
        print('Record Deleted!')

    def filterWeeklyRecords(self):
        data = self.getAllRecords(self.sheet)
        currDate = str(date.today())
        timestampDate = DateTime.getDateObj(currDate)
        lastMonday = timestampDate - timedelta(days=timestampDate.weekday())
        filtered =  list(filter(lambda x: DateTime.getDateObj(x['Date']) >= lastMonday, data))
        return filtered
    
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

sheetdb = SheetDB()
    
@bot.message_handler(commands=['progress'])
def progress(message):
    progressMap = sheetdb.roundDown(sheetdb.getWeeklyStats())
    excessMap = sheetdb.getWeeklyExcessStats()
    progressReply = sheetdb.getWeeklyStatsReply(progressMap, excessMap)
    bot.send_message(message.chat.id, progressReply)

def distance_request(message):
    if message.text:
        request = message.text.split()
        if len(request)>=2 and request[0] == "/distance" and request[1].replace('.','',1).isdigit() and float(request[1])>0:
            print('Valid distance update request!')
            return True
    return False

@bot.message_handler(func=distance_request)
def distanceReply(message):
    name = message.from_user.first_name
    bot.send_message(message.chat.id, "Good job on your run {}!".format(name))
    distance = message.text.split()[1]
    prevProgressMap = sheetdb.getWeeklyStats()
    prevWeeklyExcessStatusAboveLimit = True if prevProgressMap[name] > 10 else False
    
    sheetdb.insertRecord(name,distance)
    
    currProgressMap = sheetdb.getWeeklyStats()

    currExcess = 0
    if currProgressMap[name] > 10:
        if prevWeeklyExcessStatusAboveLimit:
            currExcess = currProgressMap[name] - prevProgressMap[name]
        else: currExcess = currProgressMap[name] - 10
        currProgressMap[name] = 10

    if currExcess>0:
        sheetdb.updateExcess(name,currExcess)

    excessMap = sheetdb.getWeeklyExcessStats()
    progressReply = sheetdb.getWeeklyStatsReply(currProgressMap, excessMap)
    
    bot.send_message(message.chat.id, progressReply)

def excess_request(message):
    if message.text and message.text == "/useexcess":
        print('Valid use excess request!')
        return True
    return False

@bot.message_handler(func=excess_request)
def distanceReply(message):
    name = message.from_user.first_name
    reply = "You have already reached your target goal of 10 km!"

    progressMap = sheetdb.getWeeklyStats()
    if progressMap[name] < 10:
        requiredDistance = 10-progressMap[name]
        scaledExcess = requiredDistance*EXCESS_FACTOR
        excessMap = sheetdb.getWeeklyExcessStats()
        if excessMap[name] < scaledExcess:
            reply = "You have not accumulated sufficient excess mileage!"
        else:
            sheetdb.insertRecord(name,requiredDistance)
            sheetdb.updateExcess(name,-1*scaledExcess)
            reply = "You have successfully redeemed your excess mileage to reach your target!"

    bot.send_message(message.chat.id, reply)

    currProgressMap = sheetdb.roundDown(sheetdb.getWeeklyStats())
    excessMap = sheetdb.getWeeklyExcessStats()
    progressReply = sheetdb.getWeeklyStatsReply(currProgressMap, excessMap)
    bot.send_message(message.chat.id, progressReply)

# def manualUpdate
# def commands (all the commands)

@bot.message_handler(commands=['hello','hey'])
def greet(message):
    bot.send_message(message.chat.id, "Hey!")
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add('Male', 'Female')
    bot.send_message(message.chat.id, str("Hi! Which one do you want? choose from the below keyboard buttons."), reply_markup=markup)

bot.polling()