
TARGETS=ConfigFrame.py

all: $(TARGETS)

PYQT_VIRTUALENV=~/pyqt4_virtualenv

PYUIC=$(PYQT_VIRTUALENV)/Scripts/python -c"import PyQt4.uic.pyuic"
#Lib/site-packages/PyQt4/pyuic4.bat

# pyuic4 is from a PyQt4 wheel install...
# https://stackoverflow.com/questions/22640640/how-to-install-pyqt4-on-windows-using-pip
# http://www.lfd.uci.edu/~gohlke/pythonlibs/#pyqt4

# Code generate Python code for PyQt4 from a Qt Designer *.ui file
%.py: %.ui
	$(PYUIC) $< -o $@

