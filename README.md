# ![PonyPixel Logo](https://raw.conep.one/ponypixel-logo-small.png) PonyPixel
Pixel place bot for Brony team at r/place 2022. The event is now over.

Thanks for those who ran PonyPixel! We succeeded. A final python script has been bundled with this final update to allow you to see the final total damage. To use it, run `python checkDamage.py`.

I have a donation page at https://ko-fi.com/cloudburstsys if you wish to donate, however it is not required at all.

Thank you soldier. Pony on.

*Note: You may see that the repository is updated occasionally. This is in preperation for a potential 2027 r/place and the first stable release of PonyPixel (we're currenly on 0.5.2 internally and we'll wanna be on 1.0.0 for the next round).*

## How to run
1. Install Python 3.7. Python version below 3.7 will NOT WORK. It **MUST** be Python 3.7 or above.
2. Install Git. This is required for you to be able to update the bot.
3. Download the bot by using the `git clone https://github.com/CloudburstSys/PonyPixel.git` command
4. Navigate to the downloaded file using `cd PonyPixel`
5. Run `pip install -r requirements.txt` or `pip3 install -r requirements.txt` to download requirements
6. Run `pip install websocket-client` or `pip3 install websocket-client` cos that one module just hates me apparently
7. Run `python -m venv env` or `python3 -m venv env`
8. If you're on Linux run `env/bin/activate`, if you're on Windows run `env/Scripts/activate.bat` or `env/Scripts/activate.ps1` (do this every new terminal/command prompt you open to run bots)
7. Run `python bot.py <username> <password>` or `python3 bot.py <username> <password>` and sit back.

## How to update
If the script detects that it's version is out of date it will prompt you to update. You are responsible for going through the install instructions again to update the bot.

Updating of the image used as reference is done automatically as part of checking for damage.
