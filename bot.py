# pip install python-telegram-bot
# pip install schedule
# pip install requests
import requests
import schedule
import telegram.bot
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters)
from telegram.ext.dispatcher import run_async
import logging
import time
from params import bottoken, port
import json
import re

bot = telegram.Bot(token=bottoken)

# pip install pyopenssl
ip = requests.get('https://api.ipify.org').text
try:
    certfile = open("cert.pem")
    keyfile = open("private.key")
    certfile.close()
    keyfile.close()
except IOError:
    from OpenSSL import crypto
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    cert = crypto.X509()
    cert.get_subject().CN = ip
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')
    with open("cert.pem", "wt") as certfile:
        certfile.write(crypto.dump_certificate(
            crypto.FILETYPE_PEM, cert).decode('ascii'))
    with open("private.key", "wt") as keyfile:
        keyfile.write(crypto.dump_privatekey(
            crypto.FILETYPE_PEM, key).decode('ascii'))

logging.basicConfig(filename='debug.log', filemode='a+', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

badset = set()
downset = set()


def loader():
    global sites
    try:
        with open('sites.json') as sitesfile:
            sites = json.load(sitesfile)
    except:
        with open('sites.json', 'w+') as sitesfile:
            sites = {}


def start(update, context):
    user = str(update.message.chat_id)
    context.bot.send_message(
        chat_id=user, text='*Website Monitoring Bot*\n_Powered by danieltan.org_\n\nReply to this message to add a site (max 5)', parse_mode=telegram.ParseMode.MARKDOWN)
    global sites
    sites[user] = []
    with open('sites.json', 'w') as sitesfile:
        json.dump(sites, sitesfile)


def addsite(update, context):
    global sites
    site = update.message.text
    user = str(update.message.chat_id)
    if len(sites[user]) == 5:
        context.bot.send_message(
            chat_id=user, text='_Max number of sites reached. Use /start to reset your list._', parse_mode=telegram.ParseMode.MARKDOWN)
        return
    try:
        r = requests.get(site, timeout=10)
        sites[user].append(site)
        with open('sites.json', 'w') as sitesfile:
            json.dump(sites, sitesfile)
        context.bot.send_message(
            chat_id=user, text='_Now monitoring_ {} _every 1 minute_'.format(site), parse_mode=telegram.ParseMode.MARKDOWN)
    except Exception as e:
        context.bot.send_message(
            chat_id=user, text='_{}_'.format(e), parse_mode=telegram.ParseMode.MARKDOWN)


@run_async
def scheduler():
    schedule.every(1).minutes.do(check)
    while True:
        schedule.run_pending()
        time.sleep(10)


def check():
    for user in sites:
        for site in sites[user]:
            ping(site, user)


@run_async
def ping(site, user):
    try:
        r = requests.get(site, timeout=10)
        if r.status_code == 200:
            if (site in badset) or (site in downset):
                badset.discard(site)
                downset.discard(site)
                bot.send_message(chat_id=user, text='*Service Restored: *{} is now online'.format(
                    site), parse_mode=telegram.ParseMode.MARKDOWN)
        else:
            code = str(r.status_code)
            if site in badset and site in downset:
                downset.discard(site)
                bot.send_message(chat_id=user, text='*Service Restored: *{} is now online with HTTP {} error'.format(
                    site, code), parse_mode=telegram.ParseMode.MARKDOWN)
            else:
                badset.add(site)
                bot.send_message(chat_id=user, text='*Incident Detected: *HTTP {} error on {}'.format(
                    code, site), parse_mode=telegram.ParseMode.MARKDOWN)
    except Exception as e:
        if site not in downset:
            downset.add(site)
            bot.send_message(chat_id=user, text='*ALERT: *{} is down\n\n_{}_'.format(site, e),
                             parse_mode=telegram.ParseMode.MARKDOWN)


@run_async
def sendnew(context, user_id, compose):
    context.bot.send_message(
        chat_id=int(user_id), text=compose, parse_mode=telegram.ParseMode.MARKDOWN)


def main():
    updater = Updater(token=bottoken, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text, addsite))

    loader()

    # updater.start_polling()
    updater.start_webhook(listen='0.0.0.0',
                          port=port,
                          url_path=bottoken,
                          key='private.key',
                          cert='cert.pem',
                          webhook_url='https://{}:{}/{}'.format(ip, port, bottoken))

    scheduler()

    print("Uptime Bot is running. Press Ctrl+C to stop.")
    updater.idle()
    print("Bot stopped successfully.")


if __name__ == '__main__':
    main()
