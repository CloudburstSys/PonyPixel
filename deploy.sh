#!/bin/bash
echo "WARNING! USE PonyPixel AT YOUR OWN RISK!"
echo "Usage of PonyPixel may result in restrictions placed on your Reddit account, banning you from placing tiles on r/place."
echo "Avoid using your main Reddit account."
echo "If you understand the risk, press enter to proceed. Ctrl+C to cancel."
read -r temp
if [ "$TERMUX_VERSION" != "" ] || [ "$TERMUX_APP_PID" != "" ] || [ "$PREFIX" == "/data/data/com.termux/files/usr" ] ; then
    echo "You are using Termux. Assuming APT and installing dependencies..."
    echo "DO NOT USE TERMUX INSTALLED FROM GOOGLE PLAY!!!"
    apt update
    apt install git python3 -y
    echo Going to /opt...
    mkdir -p "$PREFIX/opt"
    cd "$PREFIX/opt"
elif [ "$(whoami)" != "root" ] ; then
    echo "You are not running as root. System dependencies will not install."
    echo "Assuming non-root mode."
    mkdir -p ~/ponypixel
    cd ~/ponypixel
else
    echo "Testing APT (Debian/Ubuntu), DNF (Fedora/RHEL) and Pacman (Arch Linux)..."
    if [ -e "$PREFIX/bin/apt" ] ; then
        apt update
        apt install git python3 -y
        apt install python3-pip python3-venv -y
    fi
    if [ -e "$PREFIX/bin/dnf" ] ; then
        dnf install git python3 python3-pip
    fi
    if [ -e "$PREFIX/bin/pacman" ] ; then
        pacman -S git
        pacman -S python3
        pacman -S python3-pip
    fi
    echo Going to /opt...
    mkdir -p "$PREFIX/opt"
    cd "$PREFIX/opt"
fi
echo "Activating virtual environment..."
python3 -m venv env
. env/bin/activate
echo "Installing WebSocket client support..."
pip install websocket-client
pip3 install websocket-client
echo "Testing credentials..."
account=$1
password=$2
if [ "$account" == "" ] ; then
    read -p "Enter your Reddit account: " account
fi
if [ "$password" == "" ] ; then
    read -sp "Reddit password: " password
fi
printf "\n"
echo "Now let's begin the glory of us bronies!"
echo "Installing requirements will take a longer time at the first time. Please be patient."
while : ; do
    echo "Installing requirements..."
    pip install -r requirements.txt > /dev/null
    pip3 install -r requirements.txt > /dev/null
    python3 bot.py "$account" "$password"
    echo "Attempting update..."
    git pull https://github.com/CloudburstSys/PonyPixel.git
done
exit
