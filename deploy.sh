#!/bin/bash
echo "WARNING! USE PonyPixel AT YOUR OWN RISK!"
echo "Usage of PonyPixel may result in restrictions placed on your Reddit account, banning you from placing tiles on r/place."
echo "Avoid using your main Reddit account."
echo "If you understand the risk, press enter to proceed. Ctrl+C to cancel."
read -r temp
echo "Testing APT (Debian and Ubuntu) and DNF (Fedora/RHEL)..."
if [ -e "$PREFIX/bin/apt" ] ; then
    apt install git python3 python3-pip python3-venv -y
fi
if [ -e "$PREFIX/bin/dnf" ] ; then
    dnf install git python3 python3-pip
fi
if [ -e "$PREFIX/bin/pacman" ] ; then
    pacman -S git
    pacman -S python3
    pacman -S python3-pip
fi
echo "Activating virtual environment..."
python3 -m venv env
. env/bin/activate
echo "Installing requirements..."
pip install -r requirements.txt
pip3 install -r requirements.txt
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
echo "Let the defense begin!"
while : ; do
    python3 bot.py "$account" "$password"
    echo "Attempting update..."
    git pull https://github.com/CloudburstSys/PonyPixel.git
    echo "Restarting..."
done
exit
