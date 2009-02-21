#!/usr/bin/python

import getopt
import glob
import os
import re
import shutil
import sys

usage = (
"""usage: $0 [-n ngood][-bad badthresh][-d out-dir]
  [-rmbad][-rmempty][-mvbad]
  [statsum files, statlog files, or directories where they can be found]

If no statsum or statlog files are found through arguments,
./*/statsum are processed.
This is a reasonable default if mrun2.pl or runallstates.pl was used.

  -n ngood     Keep the top ngood solutions. Others may be partially or fully purged.
  -bad badthresh  Results with a Km/person score below badthresh may be purged.
  -d out-dir   Where to write out HTML and copy images to to show the best.
  -rmbad       Removes a large amount of intermediate data from bad results.
  -rmempty     Remove entirely solutions that are empty (likely solver bug)
  -mvbad       Move bad solutions (ngood or badthresh) into old/
""")

kmpp_re_a = re.compile(r".*Best Km\/p:.*Km\/p=([0-9.]+)")
kmpp_re_b = re.compile(r".*Best Km\/p: ([0-9.]+)")


class slog(object):
	def __init__(self, root, kmpp, png, text):
		self.root = root
		self.kmpp = kmpp
		self.png = png
		self.text = text
	
	def __repr__(self):
		return """slog("%s", "%s", "%s", %d chars of text)""" % (self.root, self.kmpp, self.png, len(self.text))


class manybest(object):
	def __init__(self):
		self.odir = "best"
		self.root = None
		self.slogs = []
		self.nlim = None
		self.ngood = None
		self.badkmpp = None
		self.badlist = []
		self.rmbad = False
		self.rmempty = False
		self.mvbad = False

	def addSlog(self, path):
		if self.root:
			rp = os.path.realpath(path)
			if rp.startswith(self.root):
				self.slogs.append(path[len(self.root)+1:])
			else:
				self.slogs.append(path)
		else:
			self.slogs.append(path)

	def maybeAddSlogDir(self, path):
		pa = os.path.join(path, "statsum")
		if os.access(pa, os.F_OK|os.R_OK):
			self.addSlog(pa)
			return True
		pa = os.path.join(path, "statlog")
		if os.access(pa, os.F_OK|os.R_OK):
			self.addSlog(pa)
			return True
		return False

	def setRoot(self, path):
		self.root = os.path.realpath(path)
		if not os.path.isdir(self.root):
			raise Error("-root must specify a directory")
		for f in os.listdir(self.root):
			fpath = os.path.join(self.root, f)
			if os.path.isdir(fpath) and not os.path.islink(fpath):
				self.maybeAddSlogDir(fpath)
	
	def parseOpts(self, argv):
		argv = argv[1:]
		while len(argv) > 0:
			arg = argv.pop(0)
			if arg == "-d":
				self.odir = argv.pop(0)
			elif arg == "-n":
				self.nlim = argv.pop(0)
			elif arg == "-ngood":
				self.ngood = argv.pop(0)
			elif arg == "-bad":
				self.badkmpp = argv.pop(0)
			elif (arg == "-h") or (arg == "--help"):
				print usage
				sys.exit(0)
			elif arg == "-rmbad":
				self.rmbad = True
			elif arg == "-rmempty":
				self.rmempty = True
			elif arg == "-mvbad":
				self.mvbad = True
			elif arg == "-root":
				self.setRoot(argv.pop(0))
			elif os.access(arg, os.F_OK|os.R_OK):
				self.addSlog(arg)
			elif os.path.isdir(arg) and self.maybeAddSlogDir(arg):
				pass
			else:
				errstr = "bogus arg \"%s\"\n" % arg
				sys.stderr.write(errstr)
				raise errstr
	
	def skimLogs(self, loglist=None):
		"""return (slog[] they, string[] empties)"""
		they = []
		empties = []
		if loglist is None:
			loglist = self.slogs
		for fn in loglist:
			root = os.path.dirname(fn)
			if not root:
				raise Error("could not find root of \"$fn\"\n")
			if root == "link1":
				continue
			if self.root:
				fn = os.path.join(self.root, fn)
				if not os.path.isdir(os.path.join(self.root, root)):
					continue
			else:
				if not os.path.isdir(root):
					continue
			fin = open(fn, "r")
			lines = []
			kmpp = None
			for line in fin:
				m = kmpp_re_a.match(line)
				if not m:
					m = kmpp_re_b.match(line)
				if m:
					kmpp = float(m.group(1))
					lines.append(line[1:])
				elif line[0] == "#":
					lines.append(line[1:])
			fin.close()
			if kmpp is None:
				empties.append(root)
				continue
			if self.root:
				png = os.path.join(self.root, root, "bestKmpp.png")
			else:
				png = os.path.join(root, "bestKmpp.png")
			if not os.path.isfile(png):
				sys.stderr.write("no %s\n" % png)
				continue
			if (self.badkmpp is not None) and (kmpp > self.badkmpp):
				badlist.append(root)
			they.append(slog(root, kmpp, png, "<br/>".join(lines)))
		return (they, empties)

	def copyPngs(self, they):
		i = 1
		for t in they:
			shutil.copyfile(t.png, os.path.join(self.odir, "%d.png" % i))
			i += 1
	
	def writeBestsTable(self, they, fpart):
		fpart.write("""<table border="1">""")
		i = 1
		for t in they:
			fpart.write(
				"""<tr><td><img src="%d.png"></td><td>run "%s"<br/>%s</td></tr>\n"""
				% (i, t.root, t.text))
			i += 1
			if (self.nlim is not None) and (i > self.nlim):
				break
		fpart.write("""</table>""")

	def mergeIndexParts(self):
		findex = open(os.path.join(self.odir, "index.html"), "w")
		for finame in [".head.html", ".part.html", ".tail.html"]:
			fi = open(os.path.join(self.odir, finame), "r")
			while True:
				buf = fi.read(30000)
				if len(buf) <= 0:
					break
				findex.write(buf)
			fi.close()
		findex.close()

	def setLink1(self, path):
		if os.path.exists("link1"):
			if os.path.islink("link1"):
				os.unlink("link1")
			else:
				sys.stderr.write("link1 exists but is not a link\n")
				raise Error("link1 exists but is not a link\n")
		path = os.path.realpath(path)
		if self.root:
			if path.startswith(self.root):
				os.symlink(path[len(self.root)+1:], "link1")
			else:
				os.symlink(path, "link1")
		else:
			os.symlink(path, "link1")

	def getBadlist(self, they):
		if (self.ngood is not None) and (self.ngood < len(they)):
			return [x.root for x in they[self.ngood:]]
		return None

	def rmBadlistStepdata(self, badlist):
		bgl = []
		for b in badlist:
			if self.root:
				b = os.path.join(self.root, b)
			gdir = os.path.join(b, "g")
			if os.path.exists(gdir):
				bgl.append(gdir)
			garch = os.path.join(b, "g.tar.bz2")
			if os.path.exists(garch):
				bgl.append(garch)
		if bgl:
			print "bad best kmpp:"
			print "rm -rf " + " ".join(bgl)
			for x in bgl:
				os.unlink(x)

	def moveBadToOld(self, badlist):
		print "move bad best kmpp to old dir"
		oldpath = "old"
		if self.root:
			oldpath = os.path.join(self.root, "old")
		if not os.path.isdir(oldpath):
			os.mkdir(oldpath)
		for b in badlist:
			if self.root:
				b = os.path.join(self.root, b)
			shutil.move(b, oldpath)
	
	def handleEmpties(self, empties):
		if empties:
			# don't delete the last one, in case it's still active
			empties.pop(-1)
		if empties:
			print "empty solution:"
			print "rm -rf " + " ".join(empties)
			for eroot in empties:
				if self.root:
					eroot = os.path.join(self.root, eroot)
				shutil.rmtree(eroot)
		
	def main(self, argv):
		self.parseOpts(argv)
		if (self.ngood is not None) and (self.nlim is None):
			self.nlim = self.ngood
		if not self.slogs:
			self.slogs = glob.glob("*/statsum")
		if not self.slogs:
			sys.stderr.write("no logs to process\n")
			sys.stderr.write(usage)
			sys.exit(1)
		they, empties = self.skimLogs(self.slogs)
		if not they:
			raise Exception("no good runs found\n")
		they.sort(cmp=lambda a, b: cmp(a.kmpp, b.kmpp))
		if self.odir:
			if not os.path.isdir(self.odir):
				os.makedirs(self.odir)
			self.copyPngs(they)
			fpart = open(os.path.join(self.odir, ".part.html"))
			self.writeBestsTable(they, fpart)
			fpart.close()
			self.mergeIndexParts()
			self.setLink1(they[0].root)

		badlist = self.getBadlist(they)
		if badlist:
			print "badlist: " + " ".join(badlist)
			if self.rmbad:
				self.rmBadlistStepdata(badlist)
			if self.mvbad:
				self.moveBadToOld(badlist)
		if self.rmempty and empties:
			empties.sort()
			self.handleEmpties(empties)


if __name__ == "__main__":
	it = manybest()
	it.main(sys.argv)
