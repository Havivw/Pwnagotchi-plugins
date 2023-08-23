import os
import requests
import subprocess

import wget
import discord
from pathlib import Path


TOKEN = '<YOUR_TOKEN>'
CHANNEL_ID = '<YOUR_RESULTS_CHANNEL_ID>'
CHANNEL_NAME = '<YOUR_RESULTS_CHANNEL_NAME>'
HASHCAT_PATH = '<YOUR_HASHCAT_PATH>'

HASH_CHANNEL_ID = '<YOUR_HASH_CHANNEL_ID>'
HASH_BOT_NAME = '<YOUR_HASH_BOT_NAME>'

def handle_response(message)->str:
    p_message = message.lower()
    if p_message == '!crackhash' or p_message == '!crackhelp' :
        return f"`you can use !crackhash only on channel {CHANNEL_NAME} you need to add number for scan type and number for max length of password.\n\nscan types:\n    1 : BruteForce\n    2 : numeric\n    3 : rockyou\n    4 : 10milion\n    5 : DES_full\n\nexample: !crackhash 3 8`"

async def send_message(message, user_message, is_private):
    try:
        response = handle_response(user_message)
        await message.author.send(response) if is_private else await message.channel.send(response)
    except Exception:
        pass

def run_comand(command):
    subprocess.run(command, shell=True)

def check_file(file):
    if os.path.exists(file):
        return True
    else:
        return False

def check_if_command_exists(command):
    if os.system(f"which {command}") == 0:
        return True
    else:
        return False

def download_list(): 
        my_file = Path("wordlist/rockyou.txt")
        if my_file.is_file():
            print("rockyou dict is available!")
        else:
            url = "https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt"
            wget.download(url, "wordlist/rockyou.txt")
            print("RockYou dict is downloaded!")

            my_file = Path("wordlist/10mil.txt")
        if my_file.is_file():
            print("10 million dict is available!")
        else:
            url = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10-million-password-list-top-1000000.txt"
            wget.download(url, "wordlist/10mil.txt")
            print("10 million dict is downloaded!")

            my_file = Path("wordlist/DES_full.charset")
        if my_file.is_file():
            print("DES_full.charset dict is available!")
        else:
            url = "https://raw.githubusercontent.com/brannondorsey/naive-hashcat/master/hashcat-3.6.0/charsets/DES_full.charset"
            wget.download(url, "wordlist/DES_full.charset")
            print("DES_full.charset dict is downloaded!")

def run_hashcat(filename='hashcat.22000.txt', scantype=1, maxlen=11, dict=None):
    #{1 : BruteForce, 2 : numeric, 3 : rockyou, 4 : 10milion, 5 : DES_full, 6 : custom}
    if scantype == 1:
        mask = "?a" * maxlen
        run_comand(f"{HASHCAT_PATH}hashcat -m 22000 -a 3 {filename} {mask} -i --increment-min=8")
    elif scantype == 2:
        mask = "?d" * maxlen
        run_comand(f"{HASHCAT_PATH}hashcat -m 22000 -a 3 {filename} {mask} -i --increment-min=8 ")
    elif scantype == 3:
        run_comand(f"{HASHCAT_PATH}hashcat -m 22000 -a 0 {filename} wordlist/rockyou.txt ")
    elif scantype == 4:
        run_comand(f"{HASHCAT_PATH}hashcat -m 22000 -a 0 {filename} wordlist/10mil.txt ")
    elif scantype == 5:
        run_comand(f"{HASHCAT_PATH}hashcat -m 22000 -a 0 {filename} wordlist/DES_full.charset ")
    elif scantype == 6 and dict != None:
        wget.download(dict, "wordlist/custom.dict")
        run_comand(f"{HASHCAT_PATH}hashcat -m 22000 -a 0 {filename} wordlist/custom.dict ")

def run_discord_bot():
    intents = discord.Intents.default()
    intents.messages = True
    try:
        intents.message_content = True
    except:
        pass
    client = discord.Client(intents=intents)
    @client.event
    async def on_ready():
        download_list()
        print(f'{client.user} is now ready!')
    
    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        username = str(message.author)
        user_message = str(message.content)
        channel = str(message.channel)
        print(f"{username} Said: '{user_message}' on channel:'{channel}'.")
        scantypes = {1 : 'BruteForce', 2 : 'Numeric Brute', 3 : 'RockYou', 4 : 'Common 10 Milion', 5 : 'DES_full', 6 : 'Custom'}
        if  user_message[0:10] == '!crackhash' and channel == CHANNEL_NAME:
            cmd = user_message.split(' ')
            dict = None
            try:
                scantype = int(cmd[1])
            except:
                scantype = 3
            try:
                if scantype == 6:
                    dict = cmd[2]
                maxlen = int(cmd[2])
            except:
                    maxlen = 8
            o_cahnnel = client.get_channel(HASH_CHANNEL_ID)
            messages = o_cahnnel.history(limit=100)
            async for i in messages:
                if HASH_BOT_NAME in str(i):
                    try:
                        hash_dict = i.attachments[0].to_dict()
                        attachment_url = str(hash_dict['url'])
                        break
                    except:
                        pass
            filedata = requests.get(attachment_url).text
            with open('hashcat.22000.txt', 'w') as f:
                f.write(filedata)
            if scantype == 1 or scantype == 2:
                await message.channel.send(f'''Starting to crack hashes with {scantypes[scantype]} scan type and max length of {maxlen}.''')
            elif scantype == 3 or scantype == 4 or scantype == 5:
                await message.channel.send(f'''Starting to crack hashes with {scantypes[scantype]} scan type.''')
            elif scantype == 6 and dict != None:
                await message.channel.send(f'''Starting to crack hashes with {scantypes[scantype]} scan type and custom dict {dict}.''')
            else:
                await message.channel.send(f'''Please check your command. for more informatin use !crackhelp''')
            run_hashcat(scantype=scantype, maxlen=maxlen, dict=dict)
            file_exist = check_file("hashcat.potfile")
            if file_exist:
                with open('hashcat.potfile', 'r') as f:
                    await message.channel.send(f'''Cracking is done! here is the potfile.''',file=discord.File(f, 'hashcat.potfile'))
                os.remove("hashcat.potfile")


        elif user_message[0] == '?':
            user_message = user_message[1:]
            await send_message(message=message,user_message=user_message, is_private=True)
        else:
            await send_message(message=message,user_message=user_message, is_private=False)
    client.run(TOKEN)


if __name__ == '__main__':
    run_discord_bot()
