import sys
import os
import re
import time
import random
import datetime

from mastodon import Mastodon
from PIL import Image
import numpy
import blurhash

import sqlite3
from sqlite3 import Error

MASTODON_SERVER = "https://botsin.space"

CHECK_DELAY = 30  # 30s

RANDOM_DELAY = 60 * 60  # 1 hour

last_not_id = None
last_not_check = None

last_random = None

sql_create_table = """
CREATE TABLE IF NOT EXISTS accounts (
    id text    PRIMARY KEY,
    last_image TEXT NOT NULL,
    count      INTEGER NOT NULL
);
"""

sql_insert = "INSERT OR REPLACE INTO accounts (id, last_image, count) VALUES (?, CURRENT_DATE, 0);"
sql_select = "SELECT count FROM accounts WHERE id=? AND last_image=CURRENT_DATE;"
sql_update = "UPDATE accounts SET count=count+1 WHERE id=? AND last_image=CURRENT_DATE;"


def login_app(user, pw):
    mastodon = Mastodon(client_id="pytooter_clientcred.secret", api_base_url=MASTODON_SERVER)
    mastodon.log_in(user, pw, to_file="pytooter_usercred.secret")
    print("Login for '{}' succesfull".format(user))


def create_connection(db_file):
    """create a database connection to a SQLite database"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(sqlite3.version)
    except Error as e:
        print(e)

    return conn


def create_table(conn, create_table_sql):
    """create a table from the create_table_sql statement
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)


def update_entry(conn, id):
    cur = conn.cursor()
    cur.execute(sql_select, (id,))
    row = cur.fetchone()
    if row is None:
        print("RL: inserting {}".format(id))
        cur.execute(sql_insert, (id,))
    else:
        print("RL: updating {}".format(id))
        cur.execute(sql_update, (id,))
    conn.commit()

    return cur.lastrowid


def check_entry(conn, id):
    print("RL: checking {}".format(id))
    cur = conn.cursor()
    cur.execute(sql_select, (id,))
    row = cur.fetchone()
    return row is None or row[0] < 10


def main_app():
    global last_not_check

    mastodon = Mastodon(access_token="pytooter_usercred.secret", api_base_url=MASTODON_SERVER)
    con = create_connection(r"blurbot.db")
    create_table(con, sql_create_table)

    last_not_check = datetime.datetime.now()

    while True:
        try:
            check_notifications(mastodon, con)
            make_random(mastodon)
        except Exception as e:
            print("Check exception: {}".format(e))
            time.sleep(CHECK_DELAY)


def check_notifications(mastodon, con):
    global last_not_id, last_not_check

    elapsed = datetime.datetime.now() - last_not_check
    if elapsed > datetime.timedelta(seconds=CHECK_DELAY):
        last_not_check = datetime.datetime.now()
        my_nots = mastodon.notifications(since_id=last_not_id)
        print("polled {} notifications".format(len(my_nots)))
        if len(my_nots) > 0:
            n = my_nots[0]  # get most recent notification
            last_not_id = n["id"]
            for n in my_nots:
                if check_entry(con, n["account"]["acct"]):
                    try:
                        create_hash_images(con, mastodon, n)
                    except Exception as e:
                        print("Hash exception: {}".format(e))
                else:
                    print("rate limit for {}".format(n["account"]["acct"]))
                mastodon.notifications_dismiss(n["id"])


def make_random(mastodon):
    global last_random

    if (last_random is None) or ((datetime.datetime.now() - last_random) > datetime.timedelta(seconds=RANDOM_DELAY)):
        last_random = datetime.datetime.now()

        fname = "random.jpg"
        rand_hash = randomHash()
        punch = random.random() * 10

        print("Generating random blurhash for {}".format(rand_hash))

        img = Image.fromarray(numpy.array(blurhash.decode(rand_hash, 640, 480, punch=punch)).astype("uint8"))
        img.save(fname)
        rand_media = mastodon.media_post(fname, description="Random hash: {}".format(rand_hash))

        mastodon.status_post(
            'Random hourly #blurhash image.\n\nhash: "{}"\n\npunch={}\n\n#CreativeCoding #BotsOfMastodon #GenerativeArt #RandomHourlyBlurHashImage'.format(
                rand_hash, punch
            ),
            media_ids=[rand_media["id"]],
            visibility="unlisted",
        )

        os.remove(fname)
        time.sleep(1)


# Alphabet for base 83
alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"
alphabet_values = dict(zip(alphabet, range(len(alphabet))))


def base83_decode(base83_str):
    """
    Decodes a base83 string, as used in blurhash, to an integer.
    """
    value = 0
    for base83_char in base83_str:
        value = value * 83 + alphabet_values[base83_char]
    return value


def randomHash():
    blurhash = random.choice(alphabet)

    sizeFlag = base83_decode(blurhash[0])
    numY = int(sizeFlag / 9) + 1
    numX = (sizeFlag % 9) + 1
    wanted = 4 + 2 * numX * numY

    while len(blurhash) < wanted:
        blurhash += random.choice(alphabet)

    return blurhash


def letters(input):
    return "".join([c for c in input if c in alphabet_values])


def padd_blurhash(blurhash):
    pos = 0
    while len(blurhash) < 6:
        blurhash += blurhash[pos]
        pos += 1

    sizeFlag = base83_decode(blurhash[0])
    numY = int(sizeFlag / 9) + 1
    numX = (sizeFlag % 9) + 1
    wanted = 4 + 2 * numX * numY

    pos = 0
    while len(blurhash) < wanted:
        blurhash += blurhash[pos]
        pos += 1

    if len(blurhash) > wanted:
        blurhash = blurhash[0:wanted]

    return blurhash


def create_hash_images(con, mastodon, n):
    punch_exp = re.compile(r"punch=([0-9.]+)")
    hash_exp = re.compile(r"hash=([0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz\#\$\%\*\+\,\-\.\:\;\=\?\@\[\]\^\_\{\|\}\~]+)")
    print("Got {} from {} at {}: {}".format(n["type"], n["account"]["acct"], n["created_at"], n["id"]))
    if n["type"] == "mention":

        print("-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
        print(n["account"]["display_name"] + "\n")
        print(n["account"]["acct"] + "\n")
        print(n["status"]["content"] + "\n")

        punch = 1
        m = punch_exp.search(n["status"]["content"])
        if m:
            punch = float(m[1])
            if punch < 0:
                punch = 1

        m = hash_exp.search(n["status"]["content"])
        if m:
            hash = m[1]
            hash_str = padd_blurhash(hash)
            print("hash     = {}".format(hash))
            print("hash_str = {}".format(hash_str))

            fname = "{}.jpg".format(n["id"])

            img = Image.fromarray(numpy.array(blurhash.decode(hash_str, 640, 480, punch=punch)).astype("uint8"))
            img.save(fname)
            media = mastodon.media_post(fname, description="Account name, hash: {}".format(hash_str))

            mastodon.status_reply(
                n["status"],
                'Your string as #blurhash.\n\nstring: "{}"\n\npadded hash: "{}"\n\npunch={}\n\n#CreativeCoding #BotsOfMastodon #GenerativeArt #RequestedBlurHashImage'.format(
                    hash, hash_str, punch
                ),
                media_ids=[media["id"]],
                visibility="unlisted",
            )
            update_entry(con, n["account"]["acct"])
            os.remove(fname)
        else:
            acc_str = padd_blurhash(n["account"]["acct"])
            name_str = padd_blurhash(letters(n["account"]["display_name"]))
            print("acc string={}".format(acc_str))
            print("name string={}".format(name_str))

            acc_fname = "acc_{}.jpg".format(n["id"])
            disp_fname = "disp_{}.jpg".format(n["id"])

            img = Image.fromarray(numpy.array(blurhash.decode(acc_str, 640, 480, punch=punch)).astype("uint8"))
            img.save(acc_fname)
            acc_media = mastodon.media_post(acc_fname, description="Account name, hash: {}".format(acc_str))

            img = Image.fromarray(numpy.array(blurhash.decode(name_str, 640, 480, punch=punch)).astype("uint8"))
            img.save(disp_fname)
            disp_media = mastodon.media_post(disp_fname, description="Display name, hash: {}".format(name_str))

            mastodon.status_reply(
                n["status"],
                'Your account and display name as #blurhash.\n\naccount hash: "{}"\n\ndisplay name hash: "{}"\n\npunch={}\n\n#CreativeCoding #BotsOfMastodon #GenerativeArt #AccountBlurHashImage'.format(
                    acc_str, name_str, punch
                ),
                media_ids=[acc_media["id"], disp_media["id"]],
                visibility="unlisted",
            )
            update_entry(con, n["account"]["acct"])

            os.remove(acc_fname)
            os.remove(disp_fname)
        time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "register":
        Mastodon.create_app("blurbot", api_base_url=MASTODON_SERVER, to_file="pytooter_clientcred.secret")
        print("App registered")
    elif len(sys.argv) == 4 and sys.argv[1] == "login":
        login_app(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == "run":
        main_app()
    else:
        print("Usage:")
        print("  {} [register|login|run]".format(sys.argv[0]))
