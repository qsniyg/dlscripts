import bs4
import json
import sys
import urllib.request
import urllib.parse
from dateutil.parser import parse
import time
import re
import copy
import os.path


def download(url, *args, **kwargs):
	if "head" in kwargs and kwargs["head"]:
		request = urllib.request.Request(url, method="HEAD")
	else:
		request = urllib.request.Request(url)

	request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
	request.add_header('Pragma', 'no-cache')
	request.add_header('Cache-Control', 'max-age=0')
	request.add_header('Accept-Language', 'en-US,en;q=0.9')
	request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

	with urllib.request.urlopen(request) as response:
		charset = response.headers.get_content_charset()

		read_response = response.read()
		#return read_response

		if not charset:
			return read_response

		try:
			return read_response.decode(charset)
		except Exception as e:
			return read_response


def get_domain(url):
	domain = urllib.parse.urlparse(url).netloc.lower()
	return re.sub("^www\\.", "", domain)

nopics = 0

def get_pages_match(els):
	foundmatch = False
	for el in els:
		filesregexes = [
			"^\\s*([0-9]+) (?:files|albums) on ([0-9]+) page.s.\\s*$",
			# some coppermine sites ignore accept-language and only change language based on a cookie value set in an unknown way
			"^\\s*plik.w: ([0-9]+), stron: ([0-9]+)\\s*$",
			"^\\s*([0-9]+) (?:Fotos|albuns) em ([0-9]+) p.gina.s.\\s*$",
			"^\\s*([0-9]+) photos sur ([0-9]+) page.s.\\s*$"
		]

		match = None
		for regex in filesregexes:
			match = re.search(regex, el.text)
			if match:
				break
		if match:
			return int(match.group(2))

	return None

def get_webarchive_virtual_url(url):
	return re.sub(r"^[a-z]+:\/\/[^/]+\/+web\/+[0-9]+(?:im_)?\/+(https?:)\/+", "\\1//", url)

def request_opendir(url, base_entry):
	sys.stderr.write("Requesting open directory " + url + "...\n")
	data = download(url)
	soup = bs4.BeautifulSoup(data, 'lxml')

	if "author" not in base_entry:
		base_entry["author"] = get_domain(url)

	if "album" not in base_entry:
		clean_albumurl = re.sub(r".*/images/albums/+", "", url)
		clean_albumurl = urllib.parse.unquote(re.sub(r"/+$", "", clean_albumurl))
		base_entry["album"] = " - ".join(clean_albumurl.split("/"))

	# hacky
	if "album_id" not in base_entry:
		clean_albumid = re.sub(r"/+$", "", url)
		clean_albumid = urllib.parse.unquote(os.path.basename(clean_albumid))
		base_entry["album_id"] = clean_albumid

	myjson = {
		"title": base_entry["author"],
		"author": base_entry["author"],
		"config": {
			"generator": "coppermine"
		},
		"entries": []
	}

	tr_els = soup.select("table tr")
	for el in tr_els:
		link = el.select("td > a")
		if len(link) < 1:
			continue

		link = link[0]
		if link.text == "Parent Directory":
			continue

		if link["href"].startswith("thumb_") or link["href"].startswith("normal_"):
			continue

		our_entry = copy.copy(base_entry)

		linkurl = urllib.parse.urljoin(url, link["href"])
		if linkurl.endswith("/"):
			our_entry["album_id"] = urllib.parse.unquote(link["href"].replace("/", "") + "-" + our_entry["album_id"])
			myjson["entries"] += request_opendir(linkurl, our_entry)["entries"]
			continue

		caption = re.sub(r".*\/", "", link["href"])
		caption = re.sub(r"\..*", "", caption)
		caption = urllib.parse.unquote(caption)

		date_el = el.select("td")[2]
		date = time.mktime(parse(date_el.text).timetuple())

		our_entry["images"] = [linkurl]
		our_entry["videos"] = []

		if "album_id" in our_entry:
			caption = our_entry["album_id"] + " " + caption
			del our_entry["album_id"]

		our_entry["caption"] = caption
		our_entry["date"] = date

		myjson["entries"].append(our_entry)

	return myjson

def requestpage(url, page=None, paginate=True):
	domain = get_domain(url)
	is_intceleb = domain == "internetcelebrity.org"
	is_webarchive = domain == "web.archive.org"

	virtual_url = url
	virtual_domain = domain

	#sys.stderr.write(virtual_url + " " + virtual_domain + "\n")

	if is_webarchive:
		virtual_url = get_webarchive_virtual_url(url)
		virtual_domain = get_domain(virtual_url)

	#sys.stderr.write(virtual_url + " " + virtual_domain + "\n")

	if page is None:
		pagematch = re.search("&page=([0-9]+)$", url)
		if pagematch:
			page = int(pagematch.group(1))
		else:
			page = 1

	newurl = re.sub("&page=[0-9]+", "&page=" + str(page), url)
	if "&page=" not in newurl and not is_intceleb and not is_webarchive:
		newurl = newurl + "&page=" + str(page)

	data = download(newurl)
	soup = bs4.BeautifulSoup(data, 'lxml')

	# or span.footert, remove &copy;
	# or js_vars = {...}, site_url, http://(...)/...
	authortag = soup.select("title")[0]
	author = virtual_domain
	#author = re.sub(".*- ", "", authortag.text)

	is_index = False
	albumid = re.sub(".*[?&]album=([0-9]+).*", "\\1", url)
	if is_intceleb and albumid == url:
		albumid = re.sub(".*/card-of-[^/.0-9]*?-([0-9]+)-page-[0-9]+\\..*", "\\1", url)
	if "index.php?cat=" in url and albumid == url:
		albumid = re.sub(".*[?&]cat=([0-9]+).*", "\\1", url)
		is_index = True
	if albumid == url:
		print("albumid == url")
		return None

	breadcrumbs = soup.select("table.maintable tr > td.tableh1 > span.statlink a")
	if len(breadcrumbs) == 0:
		breadcrumbs = soup.select("table.maintable tr > td > span.statlink a")
	if len(breadcrumbs) == 0:
		breadcrumbs = soup.select("table.maintable tr > td.statlink > a")
	if len(breadcrumbs) == 0:
		breadcrumbs = soup.select("table.maintable tr > td.tableh1 > a")
	orig_breadcrumb_text = []
	breadcrumb_text = []

	for crumb in breadcrumbs:
		if "?" in crumb["href"]:
			our_text = crumb.text.strip()
			orig_breadcrumb_text.append(our_text)

			# "photos - photos 2020" -> "photos - 2020"
			if len(breadcrumb_text) > 0 and our_text.startswith(breadcrumb_text[-1]):
				our_text = our_text[len(breadcrumb_text[-1]):].strip()
			breadcrumb_text.append(our_text)

	albumtitle = " - ".join(breadcrumb_text)
	oldalbumtitle = " - ".join(orig_breadcrumb_text)
	if not albumtitle or len(albumtitle) == 0:
		if is_intceleb:
			albumtitle = soup.select("ul > li > h1.title")[0].text
			oldalbumtitle = albumtitle

		if not albumtitle or len(albumtitle) == 0:
			sys.stderr.write("No album title!\n")
			return None

	myjson = {
		"title": author,
		"author": author,
		"config": {
			"generator": "coppermine"
		},
		"entries": []
	}

	categories = []
	if is_index:
		categories = soup.select("table.maintable > tr > td > table > tr > td > span.catlink > a")

	linkid = 0
	for category in categories:
		linkid += 1
		linkel = category
		if "index.php?cat=" in linkel["href"]:
			sys.stderr.write("Requesting category " + linkel["href"] + " (" + str(linkid) + "/" + str(len(categories)) + ")\n")
			linkurl = urllib.parse.urljoin(url, linkel["href"])
			albumjson = requestpage(linkurl, None)
			myjson["entries"] += albumjson["entries"]
			continue

	images = []
	if is_index:
		images = soup.select("table.maintable table > tr > td > span.alblink > a")
		if len(images) == 0:
			images = soup.select("table.maintable table > tr > td.albthumbnails > a")
	else:
		images = soup.select("td.thumbnails td > a > img")
		if len(images) == 0:
			images = soup.select("td.thumbnails td > a > div.thumbcontainer > img")
		if len(images) == 0 and is_intceleb:
			images = soup.select(".panel-body > .tab-content > .container-fluid div > a > img")

	if len(images) > 0:
		linkid = 0
		for image in images:
			linkel = image
			if linkel.name != "a":
				linkel = image.parent

			linkid += 1

			if linkel.name.lower() == "a":
				if "thumbnails.php?album=" in linkel["href"]:
					sys.stderr.write("Requesting album " + linkel["href"] + " (" + str(linkid) + "/" + str(len(images)) + ")\n")
					linkurl = urllib.parse.urljoin(url, linkel["href"])

					try:
						albumjson = requestpage(linkurl, None)
						myjson["entries"] += albumjson["entries"]
					except Exception as e:
						if is_webarchive:
							image_el = image
							if image_el.name != "img":
								while image_el and image_el.name != "table":
									image_el = image_el.parent
								image_el = image_el.select("a > img")[0]
							opendirname = os.path.dirname(get_webarchive_virtual_url(urllib.parse.urljoin(url, image_el["src"]))) + "/"
							base_entry = {
								"album_id": re.sub(".*[?&]album=([0-9]+).*", "\\1", linkel["href"]),
								"album": albumtitle + " - " + linkel.text,
								"author": author,
								"videos": []
							}
							opendir_entries = request_opendir(opendirname, base_entry)
							myjson["entries"] += opendir_entries["entries"]
							#print(json.dumps(opendir_entries))
							#print(json.dumps(base_entry))
						else:
							raise e
					continue

			if is_index:
				# e.g. last additions, last viewed...
				#sys.stderr.write("skipping\n")
				continue

			image_entries = []

			if re.search("^(?:\\.*\/)?images/thumbs/(?:t(?:humb)?_)?nopic\\.png$", image["src"]):
				global nopics
				nopics += 1
				continue

			# t_ is present in coppermine 1.5.24
			imageurl = urllib.parse.urljoin(url, re.sub("/t(?:humb)?_([^/.?#]+\\.)", "/\\1", image["src"]))
			if is_webarchive:
				imageurl = get_webarchive_virtual_url(imageurl)
			image_entries.append(imageurl)

			# often fails or returns the wrong image, but sometimes returns a larger image (probably due to user error)... keep?
			norm_imageurl = urllib.parse.urljoin(url, re.sub("/normal_([^/.?#]+\\.)", "/\\1", imageurl))
			if norm_imageurl != imageurl:
				image_entries.append(norm_imageurl)

			for imageurl in image_entries:
				imageurls = []
				imageurls.append(imageurl)
				if ".JPG" in imageurl:
					imageurls.append(imageurl.replace(".JPG", ".jpg"))
				elif ".jpg" in imageurl:
					imageurls.append(imageurl.replace(".jpg", ".JPG"))

				caption = re.sub(".*/([^/.?#]+)\\..*", "\\1", imageurl)
				caption = albumid + " " + caption

				date = 0
				dateaddedre = re.search("(?:Date added|Data Envio|Ajouté le)(?:=|\\s*:\\s*)([a-zA-Zû, 0-9]+)", image["title"])
				if dateaddedre:
					dateaddedtxt = dateaddedre.groups(0)[0]
					dateaddedtxt = (dateaddedtxt
						# portugese
						.replace("Mai", "May")
						.replace("Set", "September")
						# french
						.replace("Août", "August"))
					date = time.mktime(parse(dateaddedtxt).timetuple())

				myjson["entries"].append({
					"caption": caption,
					"date": date,
					"album": albumtitle,
					"similaralbum": oldalbumtitle,
					"author": author,
					"images": [imageurls],
					"videos": []
				})

		pageselectors = [
			"tr > td > table > tr > td",
			"tr > td > table > tr > div.albpagebottom > div.albpagebottomtext"
		]

		totalpages = 1
		foundmatch = False
		for selector in pageselectors:
			newpages = get_pages_match(soup.select(selector))
			if newpages is not None:
				totalpages = newpages
				foundmatch = True
				break;

		if not foundmatch:
			sys.stderr.write("Unable to find pages match\n")

		if paginate is True and page < totalpages:
			sys.stderr.write("Requesting page " + str(page+1) + "/" + str(totalpages) + "\n")
			nextpagejson = requestpage(url, page+1)
			myjson["entries"] += nextpagejson["entries"]

	return myjson


if __name__ == "__main__":
	url = sys.argv[1]
	paginate = True
	is_opendir = False
	if len(sys.argv) > 2:
		if sys.argv[2] == "nopaginate":
			paginate = False
		elif sys.argv[2] == "opendir":
			is_opendir = True

	if is_opendir:
		print(json.dumps(request_opendir(url, {})))
		sys.exit()

	page = 1
	pagematch = re.search("&page=([0-9]+)$", url)
	if pagematch:
		page = int(pagematch.group(1))
	# todo: None instead of page
	myjson = requestpage(url, page, paginate)
	if nopics > 0:
		sys.stderr.write("Skipped " + str(nopics) + " blank images\n")
	print(json.dumps(myjson))
