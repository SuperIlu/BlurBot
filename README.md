# BlurBot
This is the Python source for the [BlurBot](https://botsin.space/@blurbot) on Mastodon.

This bot creates a random [blurhash](https://blurha.sh/) image each hour.

This bot also creates images based on your user and display name if you mention it in a toot.

The punch parameter can be used to de- or increase the contrast of the
resulting image. Just add `punch=<number>` to your toot (number >= 1).

There is a rate limit of one image request per day per account.

It may not be running 24/7!

This bot was created by [@dec_hl](https://mastodon.social/@dec_hl)

# Used packages
- Mastodon.py
- PIL
- numpy
- blurhash
- sqlite3
