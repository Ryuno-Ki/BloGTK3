PYTHON ?= python2.6
INSTALL ?= install
RM ?= rm
MSGFMT ?= msgfmt
MSGMERGE ?= msgmerge
XGETTEXT ?= xgettext
FIND ?= find

# autodetect GNOME prefix, change this if you want it elsewhere
PREFIX ?= `pkg-config libgnome-2.0 --variable=prefix || echo /usr`

BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/share/blogtk2/lib/blogtk2/
DATADIR = $(PREFIX)/share/blogtk2/glade
RESDIR = $(PREFIX)/share/blogtk2/res
I18NDIR = $(PREFIX)/share/blogtk2/i18n
APPLICATIONSDIR = $(PREFIX)/share/applications
ICONDIR = $(PREFIX)/share/pixmaps

PYFILES := $(shell $(FIND) . -name "*.py" -print)

install: 
	$(INSTALL) -m 755 -d $(BINDIR) $(LIBDIR) $(DATADIR) $(RESDIR) $(I18NDIR) $(APPLICATIONSDIR) $(ICONDIR)
	$(INSTALL) -m 755 bin/blogtk2 $(BINDIR)
	$(INSTALL) -m 644 share/blogtk2/lib/blogtk2/* $(LIBDIR)
	$(INSTALL) -m 644 share/blogtk2/glade/*.glade $(DATADIR)
	$(INSTALL) -m 644 share/blogtk2/res/*.png $(RESDIR)
	$(INSTALL) -m 644 data/blogtk-icon.png $(ICONDIR)
	$(INSTALL) -m 644 data/blogtk.desktop $(APPLICATIONSDIR)



