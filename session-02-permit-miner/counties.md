# Where to get permits for your area

Building permits are public records. Most large US counties and cities
publish them on a free open-data portal, and nearly all of those
portals run the same software, so this miner reads any of them from
just two values.

You need a **portal** and a **dataset**, and both go in `config.yml`.

---

## Finding yours in about two minutes

1. Google **"<your county> open data building permits"**. Add the state
   if your county name is common.
2. You want a government page with an **API** or **Export** button on
   it, not a PDF and not a search form.
3. Look at the web address of that dataset page:

   ```
   https://data.yourcounty.gov/Housing/Building-Permits/ab12-cd34
           ^^^^^^^^^^^^^^^^^^^^                        ^^^^^^^^^
           portal                                      dataset
   ```

4. Put those two values into `config.yml`:

   ```yaml
   permit_source:
     place: "Your County, ST"
     portal: "data.yourcounty.gov"
     dataset: "ab12-cd34"
   ```

**Check it before class if you can.** Paste this into your browser,
swapping in your two values:

```
https://PORTAL/resource/DATASET.json?$limit=1
```

If you get back a block of text full of `{` and `}`, you are set. If
you get an error page, the dataset id is wrong.

---

## Starting points

These are large jurisdictions that publish building permits on an
open-data portal. **Spot-check the one you pick** using the link
pattern above before you rely on it: open-data portals retire and
renumber datasets without notice, and the value column in particular
varies a lot.

| Area | portal | dataset |
|---|---|---|
| Austin, TX (default) | `data.austintexas.gov` | `3syk-w9eu` |
| Chicago, IL | `data.cityofchicago.org` | `ydr8-5enu` |
| Los Angeles, CA | `data.lacity.org` | `nbyu-2ha9` |
| New York City, NY | `data.cityofnewyork.us` | `ipu4-2q9a` |
| Seattle, WA | `data.seattle.gov` | `76t5-zqzr` |

If your area is not on a portal at all, that is a real finding and not
a failure. Plenty of counties still run permits on paper or behind a
search form that cannot be read automatically. Leave the default in
place, watch how the scoring behaves on Austin's permits, and you will
still learn the part that matters.

---

## Optional: a free app token

Portals limit how often an anonymous visitor can ask for data. During a
workshop, fifty people asking at once can trip that limit.

A free app token raises it. It is optional, it takes about two minutes,
and everything works without it.

1. Go to the portal's developer page, usually
   `https://PORTAL/profile/app_tokens` (sign up for a free account).
2. Create an app token and copy it.
3. In YOUR fork: **Settings > Secrets and variables > Actions > New
   repository secret**, named exactly `SOCRATA_APP_TOKEN`.

If the secret is there, the miner uses it. If not, it carries on
without it.

---

## Why permits and not a lead list

A permit is not a name someone sold you. It is a public record that a
homeowner has already decided to spend the money and already been
approved to start. The work is scheduled. The budget exists. Almost
nobody in this trade reads them.
