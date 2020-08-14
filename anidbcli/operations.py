from abc import ABC, abstractmethod
import os
import datetime
import re
import glob
import errno
import time

import warnings
warnings.filterwarnings("ignore",category=UserWarning,module="fuzzywuzzy")
import fuzzywuzzy.process

import anidbcli.libed2k as libed2k 

# ed2k,md5,sha1,crc32,resolution,aired,year,romanji,kanji,english,epno,epname,epromanji,epkanji,groupname,shortgroupname
API_ENDPOINT_FILE = "FILE size=%d&ed2k=%s&fmask=79FAFFE900&amask=F2FCF0C0"
API_ENDPOINT_FILE_ONLY_ANIMEINFO = "FILE size=%d&ed2k=%s&fmask=0000000000&amask=F2FCF0C0"


API_ENDPOINT_MYLYST_ADD = "MYLISTADD size=%d&ed2k=%s&viewed=%d&state=%s"
API_ENDPOINT_MYLYST_EDIT = "MYLISTADD size=%d&ed2k=%s&edit=1&viewed=%d&state=%s"

RESULT_FILE = 220
RESULT_MYLIST_ENTRY_ADDED = 210
RESULT_MYLIST_ENTRY_EDITED = 311
RESULT_ALREADY_IN_MYLIST = 310


def IsNullOrWhitespace(s):
        return s is None or s.isspace() or s == ""

class Operation:
    @abstractmethod
    def Process(self, file): pass

class MylistAddOperation(Operation):
    def __init__(self, connector, output, state, unwatched):
        self.connector = connector
        self.output = output
        self.state = state 
        if unwatched:
            self.viewed = 0
        else:
            self.viewed = 1
    def Process(self, file):
        try:
            res = self.connector.send_request(API_ENDPOINT_MYLYST_ADD % (file["size"], file["ed2k"], self.viewed, int(self.state)))
            if res["code"] == RESULT_MYLIST_ENTRY_ADDED:
                self.output.success("Mylist entry added.")
            elif res["code"] == RESULT_ALREADY_IN_MYLIST:
                self.output.warning("Already in mylist.")
                res = self.connector.send_request(API_ENDPOINT_MYLYST_EDIT % (file["size"], file["ed2k"], self.viewed, int(self.state)))
                if res["code"] == RESULT_MYLIST_ENTRY_EDITED:
                    self.output.success("Mylist entry state updated.")
                else:
                    self.output.warning("Could not mark as watched.")
            else:
                self.output.error("Couldn't add to mylist: %s" % res["data"])
        except Exception as e:
            self.output.error("Failed to add file to mylist: " + str(e))

        return True

class HashOperation(Operation):
    def __init__(self, output, show_ed2k):
        self.output = output
        self.show_ed2k = show_ed2k
    def Process(self, file):
        try:
            link = libed2k.hash_file(file["path"])
        except Exception as e:
            self.output.error("Failed to generate hash: " + str(e))
            return False
        file["ed2k"] = link
        file["size"] = os.path.getsize(file["path"])
        self.output.success("Generated ed2k link.")
        if self.show_ed2k:
            self.output.info(libed2k.get_ed2k_link(file["path"], file["ed2k"]))
        return True


class GetFileInfoOperation(Operation):
    def __init__(self, connector, output):
        self.connector = connector
        self.output = output


    def Process(self, file):
        try:
            res = self.connector.send_request(API_ENDPOINT_FILE % (file["size"], file["ed2k"]))
        except Exception as e:
            self.output.error("Failed to get file info: " + str(e))
            return False
        if res["code"] != RESULT_FILE:
            self.output.error("Failed to get file info: %s" % res["data"])
            return False
        parsed = parse_data(res["data"].split("\n")[1])
        if len(parsed) < 42:
            try:
                parsed = parsed[:25] # Take file info only
                time.sleep(2) # UDP API allows max one request per 2 seconds
                res = self.connector.send_request(API_ENDPOINT_FILE_ONLY_ANIMEINFO % (file["size"], file["ed2k"]))
                parsed = parsed + parse_data(res["data"].split("\n")[1])[1:] # Add new anime info (file id on index 0)
            except Exception as e:
                self.output.error("Failed to get file info: " + str(e))
                return False
            if res["code"] != RESULT_FILE:
                self.output.error("Failed to get file info: %s" % res["data"])
                return False

        fileinfo = {}
        fileinfo["fid"] = parsed[0]
        fileinfo["aid"] = parsed[1]
        fileinfo["eid"] = parsed[2]
        fileinfo["gid"] = parsed[3]
        fileinfo["lid"] = parsed[4]
        fileinfo["file_state"] = parsed[5]
        fileinfo["size"] = parsed[6]
        fileinfo["ed2k"] = parsed[7]
        fileinfo["md5"] = parsed[8]
        fileinfo["sha1"] = parsed[9]
        fileinfo["crc32"] = parsed[10]
        fileinfo["color_depth"] = parsed[11]
        fileinfo["quality"] = parsed[12]
        fileinfo["source"] = parsed[13]
        fileinfo["audio_codec"] = parsed[14]
        fileinfo["audio_bitrate"] = parsed[15]
        fileinfo["video_codec"] = parsed[16]
        fileinfo["video_bitrate"] = parsed[17]
        fileinfo["resolution"] = parsed[18]
        fileinfo["filetype"] = parsed[19]
        fileinfo["dub_language"] = parsed[20]
        fileinfo["sub_language"] = parsed[21]
        fileinfo["length"] = parsed[22]
        fileinfo["aired"] = datetime.datetime.fromtimestamp(int(parsed[23]))
        fileinfo["filename"] = parsed[24]
        fileinfo["ep_total"] = parsed[25]
        fileinfo["ep_last"] = parsed[26]
        fileinfo["year"] = parsed[27]
        fileinfo["a_type"] = parsed[28]
        fileinfo["a_categories"] = parsed[29]
        fileinfo["a_romaji"] = parsed[30]
        fileinfo["a_kanji"] = parsed[31]
        fileinfo["a_english"] = parsed[32]
        fileinfo["a_other"] = parsed[33]
        fileinfo["a_short"] = parsed[34]
        fileinfo["a_synonyms"] = parsed[35]
        fileinfo["ep_no"] = parsed[36]
        fileinfo["ep_english"] = parsed[37]
        fileinfo["ep_romaji"] = parsed[38]
        fileinfo["ep_kanji"] = parsed[39]
        fileinfo["g_name"] = parsed[40]
        fileinfo["g_sname"] = parsed[41]
        fileinfo["version"] = ""
        fileinfo["censored"] = ""

        status = int(fileinfo["file_state"])
        if status & 4: fileinfo["version"] = "v2"
        if status & 8: fileinfo["version"] = "v3"
        if status & 16: fileinfo["version"] = "v4"
        if status & 32: fileinfo["version"] = "v5"
        if status & 64: fileinfo["censored"] = "uncensored"
        if status & 128: fileinfo["censored"] = "censored"

        if IsNullOrWhitespace(fileinfo["ep_english"]):
            fileinfo["ep_english"] = fileinfo["ep_romaji"]
        if IsNullOrWhitespace(fileinfo["a_english"]):
            fileinfo["a_english"] = fileinfo["a_romaji"]

        file["info"] = construct_helper_tags(fileinfo)
        self.output.success("Successfully grabbed file info.")
        return True

class RenameOperation(Operation):
    def __init__(self, output, target_path, date_format, delete_empty, keep_structure, soft_link, hard_link, abort):
        self.output = output
        self.target_path = target_path
        self.date_format = date_format
        self.delete_empty = delete_empty
        self.keep_structure = keep_structure
        self.soft_link = soft_link
        self.hard_link = hard_link
        self.abort = abort
    def Process(self, file):
        try:
            file["info"]["aired"] = file["info"]["aired"].strftime(self.date_format)
        except:
            self.output.warning("Invalid date format, using default one instead.")
            try:
                file["info"]["aired"] = file["info"]["aired"].strftime("%Y-%m-%d")
            except:
                pass # Invalid input format, leave as is
        target = self.target_path
        for tag in file["info"]:
            if (self.abort and ("%"+tag+"%" in target) and IsNullOrWhitespace(file["info"][tag])):
                self.output.error("Rename aborted, " + tag + " is empty.")
                return
            target = target.replace("%"+tag+"%", filename_friendly(file["info"][tag])) # Remove path invalid characters
        target = ' '.join(target.split()) # Replace multiple whitespaces with one
        filename, base_ext = os.path.splitext(file["path"])
        for f in glob.glob(glob.escape(filename) + "*"): # Find subtitle files
            try:
                tmp_tgt = target
                if self.keep_structure: # Prepend original directory if set
                    tmp_tgt = os.path.join(os.path.dirname(f),target)
                _, file_extension = os.path.splitext(f)
                try:
                    os.makedirs(os.path.dirname(tmp_tgt + file_extension))
                except:
                    pass
                if self.soft_link:
                    os.symlink(f, tmp_tgt + file_extension)
                    self.output.success("Created soft link: \"%s\"" % (tmp_tgt + file_extension))
                elif self.hard_link:
                    os.link(f, tmp_tgt + file_extension)
                    self.output.success("Created hard link: \"%s\"" % (tmp_tgt + file_extension))
                else:
                    os.rename(f, tmp_tgt + file_extension)
                    self.output.success("File renamed to: \"%s\"" % (tmp_tgt + file_extension))
            except:
                self.output.error("Failed to rename/link to: \"%s\"" % (tmp_tgt + file_extension) + "\n")
        if self.delete_empty and len(os.listdir(os.path.dirname(file["path"]))) == 0:
            os.removedirs(os.path.dirname(file["path"]))
        file["path"] = target + base_ext

def filename_friendly(input):
    replace_with_space = ["<", ">", "/", "\\", "*", "|"]
    for i in replace_with_space:
        input = input.replace(i, " ")
    input = input.replace("\"", "'")
    input = input.replace(":","")
    input = input.replace("?","")
    return input

def parse_data(raw_data):
    res = raw_data.split("|")
    for idx, item in enumerate(res):
        item = item.replace("'", "§") # preseve lists by converting UDP list delimiter ' to § (§ seems unused in AniDB)        
        item = item.replace("<br />", "\n")
        item = item.replace("/", "|")
        item = item.replace("`", "'")
        res[idx] = item
    return res

def construct_helper_tags(fileinfo):
    year_list = re.findall('(\d{4})', fileinfo["year"])
    if (len(year_list) > 0):
        fileinfo["year_start"] = year_list[0]
        fileinfo["year_end"] = year_list[-1]
    else:
        fileinfo["year_start"] = fileinfo["year_end"] = fileinfo["year"]

    res_match = re.findall('x(360|480|720|1080|2160)', fileinfo["resolution"])
    if (len(res_match) > 0):
        fileinfo["resolution_abbr"] = res_match[0] + 'p'
    else:
        fileinfo["resolution_abbr"] = fileinfo["resolution"]

    # try to find "good" alternative series names from (a_other, a_synonyms, a_short)
    combo_names_list = fileinfo["a_other"].split('§') + fileinfo["a_synonyms"].split('§') + fileinfo["a_short"].split('§')
    alt_names_list = list(filter(lambda x: x.isascii(), combo_names_list))
    a_english_alt_tuplist = fuzzywuzzy.process.extractBests(fileinfo["a_english"], alt_names_list, score_cutoff=30, limit=15)
    a_romaji_alt_tuplist = fuzzywuzzy.process.extractBests(fileinfo["a_romaji"], alt_names_list, score_cutoff=30, limit=15)
    # build, extract short/shorter "decent" name
    fileinfo["a_english_short"] = next(filter(lambda x: len(x[0]) < 40 and len(x[0]) < len(fileinfo["a_english"]), a_english_alt_tuplist), (fileinfo["a_english"],100))[0]
    fileinfo["a_romaji_short"] = next(filter(lambda x: len(x[0]) < 40 and len(x[0]) < len(fileinfo["a_romaji"]), a_romaji_alt_tuplist), (fileinfo["a_romaji"],100))[0]
    fileinfo["a_english_shorter"] = next(filter(lambda x: len(x[0]) < 12 and len(x[0]) < len(fileinfo["a_english"]), a_english_alt_tuplist), (fileinfo["a_english"],100))[0]
    fileinfo["a_romaji_shorter"] = next(filter(lambda x: len(x[0]) < 12 and len(x[0]) < len(fileinfo["a_romaji"]), a_romaji_alt_tuplist), (fileinfo["a_romaji"],100))[0]
    # remove 100% matches
    a_english_alt_tuplist = list(filter(lambda x: x[1] < 100, a_english_alt_tuplist))
    a_romaji_alt_tuplist = list(filter(lambda x: x[1] < 100, a_romaji_alt_tuplist))
    # get best alternative name match
    if (len(a_english_alt_tuplist) > 0):
        fileinfo["a_english_alt"] = a_english_alt_tuplist[0][0]
    else:
        fileinfo["a_english_alt"] = fileinfo["a_english"]

    if (len(a_romaji_alt_tuplist) > 0):
        fileinfo["a_romaji_alt"] = a_romaji_alt_tuplist[0][0]
    else:
        fileinfo["a_romaji_alt"] = fileinfo["a_romaji"]
    return fileinfo
