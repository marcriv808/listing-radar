# Terms of Use and Privacy Policy

**Version 1** — 2026-08-11

These terms cover `listing-radar`, a command-line tool that reads public Etsy
listing data. Accept them with `listing-radar accept-terms` before first use.

## The short version

This tool runs entirely on your machine, using an Etsy API key you register
yourself. It never sends your data anywhere except to Etsy, it never writes to
your shop, and it has no server, no account, and no telemetry.

## Who provides this

listing-radar is provided solely by Marc Rivera (the "Application Developer").
Support: marc@listingresearchos.com

DISCLAIMER: THIS APPLICATION IS SOLELY PROVIDED BY MARC RIVERA (THE
"APPLICATION DEVELOPER"). YOU ACKNOWLEDGE THAT ETSY, INC. AND ITS AFFILIATES
ARE NOT THE APPLICATION DEVELOPER, DO NOT PROVIDE THE APPLICATION SERVICE, AND
MAKE NO WARRANTIES OF ANY KIND WITH RESPECT TO THE APPLICATION OR DATA
ACCESSED THROUGH IT.

The term 'Etsy' is a trademark of Etsy, Inc. This Application uses Etsy's API,
but is not endorsed or certified by Etsy.

## Your Etsy API key

You supply your own Etsy API credentials through environment variables. You are
responsible for keeping them secure and for your own compliance with Etsy's
[API Terms of Use](https://www.etsy.com/legal/api/), which apply to you
directly as the key holder.

The tool reads your credentials from the environment at runtime. It never
writes them to disk, never transmits them anywhere except in the `x-api-key`
header of requests to `openapi.etsy.com`, and never logs them.

## What data this handles, and where it goes

| Data | Where it goes | How long it is kept |
|---|---|---|
| Your API credentials | environment → Etsy request headers | never stored |
| Etsy listing/shop responses | `~/.cache/listing-radar` on your machine | 6 hours |
| Your search phrases | sent to Etsy as query parameters | not stored by this tool |
| Anything else | nowhere | n/a |

There is no analytics, no telemetry, no crash reporting, no remote logging, and
no network destination other than Etsy's API. The developer receives nothing
about your usage and cannot see what you search for.

The 6-hour cache lifetime is set by Etsy's API Terms §5, which caps how stale
displayed listing content may be. Delete `~/.cache/listing-radar` at any time.

## Read-only

This tool issues only HTTP GET requests. It contains no POST, PATCH, PUT, or
DELETE call, no OAuth flow, and no `Authorization` header. This is enforced by
an automated test that parses the source tree and fails the build if any write
call or auth header appears. It cannot modify your shop, your listings, or
anyone else's.

## Accuracy — read this one

The scoring formulas are **unvalidated heuristics**. They have not been
backtested against sales outcomes and no claim is made that they predict
anything.

`rank` positions come from the API's keyword relevance search, which is **not**
buyer-facing Etsy search ranking. A position is ordinal evidence only.

Do not treat this tool's output as a basis for a financial decision without
your own judgement. If a number looks wrong, it may well be: email
marc@listingresearchos.com with the phrase and listing id.

## No warranty

Provided "as is", without warranty of any kind, under the MIT License in
`LICENSE`. To the maximum extent permitted by law, the Application Developer
is not liable for any claim, damages, or other liability arising from use of
this software.

## Changes

Material changes bump the version at the top of this file, and the tool will
ask you to accept again. Acceptance records only the version number and a
timestamp, in `~/.cache/listing-radar/accepted-terms.json`, on your machine.

## Contact

marc@listingresearchos.com
