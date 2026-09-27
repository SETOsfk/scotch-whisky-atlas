# Load the Scotch whisky flavour atlas and the Whisky Advocate score list — R twin of python/whisky/data.py.
# Base R only; every naming rule lives in data/reference/*.csv so both languages read the same tables.

if (!isTRUE(l10n_info()[["UTF-8"]])) invisible(Sys.setlocale("LC_CTYPE", "C.UTF-8"))

project_root <- function() {
  here <- normalizePath(".")
  for (i in 1:4) {
    if (file.exists(file.path(here, "data", "atlas", "WhiskyOut.kml"))) return(here)
    here <- dirname(here)
  }
  stop("Run from the repository (or a sub-folder of it).")
}

ROOT <- project_root()
REF <- file.path(ROOT, "data", "reference")
KML <- file.path(ROOT, "data", "atlas", "WhiskyOut.kml")
REVIEWS <- file.path(ROOT, "data", "raw", "scotch_review2020.csv")
FLAVOURS <- c("Body", "Sweetness", "Smoky", "Medicinal", "Tobacco", "Honey",
              "Spicy", "Winey", "Nutty", "Malty", "Fruity", "Floral")
ISLAY <- sprintf("PA%d", 42:49)                          # Islay postcode districts
OTHER_BRANDS <- "octomore|port charlotte|ballechin"      # peated brands made at an atlas distillery

load_atlas <- function(path = KML) {
  s <- paste(readLines(path, encoding = "UTF-8", warn = FALSE), collapse = "\n")
  pms <- regmatches(s, gregexpr("(?s)<Placemark>.*?</Placemark>", s, perl = TRUE))[[1]]
  rows <- lapply(pms, function(pm) {
    kv <- regmatches(pm, gregexpr('<SimpleData name="[^"]+">[^<]*</SimpleData>', pm))[[1]]
    v <- setNames(sub('.*">([^<]*)</SimpleData>', "\\1", kv), sub('<SimpleData name="([^"]+)">.*', "\\1", kv))
    xy <- as.numeric(strsplit(sub("(?s).*<coordinates>([^<]+)</coordinates>.*", "\\1", pm, perl = TRUE), ",")[[1]][1:2])
    data.frame(raw = v[["Distillery"]], postcode = trimws(v[["Postcode"]]), lat = xy[2], lon = xy[1],
               as.list(setNames(as.integer(v[FLAVOURS]), FLAVOURS)))
  })
  df <- do.call(rbind, rows)
  names_tbl <- read.csv(file.path(REF, "distillery_names.csv"), colClasses = "character", na.strings = character())
  df$distillery <- ifelse(df$raw %in% names_tbl$raw, names_tbl$display[match(df$raw, names_tbl$raw)], df$raw)
  own <- names_tbl$pattern[match(df$distillery, names_tbl$display)]
  df$pattern <- ifelse(!is.na(own) & own != "", own, paste0("\\b", gsub(" ", " ?", tolower(df$distillery)), "\\b"))
  df$islay <- substr(df$postcode, 1, 4) %in% ISLAY
  df$style <- style_of(df)
  df <- df[order(tolower(df$distillery), method = "radix"), ]
  rownames(df) <- NULL
  df
}

style_of <- function(d) {                                  # first rule that fires, rules of thumb
  ifelse(d$Smoky >= 3 | d$Medicinal >= 2, "peated",
         ifelse(d$Winey >= 3, "sherried",
                ifelse(d$Body <= 1 & d$Smoky <= 1, "light", "honeyed")))
}

haversine_km <- function(lat, lon) {
  la <- lat * pi / 180; lo <- lon * pi / 180
  a <- sin(outer(la, la, "-") / 2)^2 + outer(cos(la), cos(la)) * sin(outer(lo, lo, "-") / 2)^2
  2 * 6371 * asin(sqrt(pmin(pmax(a, 0), 1)))
}

parse_price <- function(s) {                               # "1,500" → 1500; "50/375ml." → 100; "60,000/set" → NA
  s <- trimws(gsub(",", "", s))
  num <- suppressWarnings(as.numeric(sub("^\\$?(\\d+(\\.\\d+)?).*$", "\\1", s)))
  num[!grepl("^\\$?\\d", s) | grepl("set", tolower(s))] <- NA
  ifelse(grepl("375", s), num * 2, num)
}

last_match <- function(x, pattern) vapply(regmatches(x, gregexpr(pattern, x, perl = TRUE)),
                                          function(m) if (length(m)) m[length(m)] else NA_character_, "")

load_reviews <- function(path = REVIEWS, atlas = load_atlas()) {
  df <- read.csv(path, colClasses = "character", encoding = "UTF-8", na.strings = character())
  names(df) <- c("id", "name", "category", "points", "price_raw", "currency", "description")
  df$points <- as.integer(df$points)
  df$name <- trimws(gsub("’", "'", df$name))
  df$price_usd <- parse_price(df$price_raw)
  abv <- as.numeric(sub("\\s*%$", "", last_match(df$name, "\\d{2}(?:\\.\\d+)?\\s*%")))
  df$abv <- ifelse(!is.na(abv) & abv >= 35 & abv <= 75, abv, NA)
  m <- regexpr("(?i)\\d{1,2}\\s*[- ]?year[- ]old", df$name, perl = TRUE)
  df$age <- NA_real_
  df$age[m > 0] <- as.numeric(sub("^(\\d{1,2}).*", "\\1", regmatches(df$name, m)))
  df$distillery <- link(df, atlas)
  df
}

link <- function(df, atlas) {                               # earliest named atlas distillery in a single-malt title
  keep <- atlas$pattern != "none"
  pats <- atlas$pattern[keep]; dist <- atlas$distillery[keep]
  low <- tolower(df$name)
  pos <- sapply(pats, function(p) { r <- regexpr(p, low, perl = TRUE); ifelse(r > 0, r, NA) })
  out <- apply(pos, 1, function(r) { if (all(is.na(r))) return(NA_character_)
    h <- which(!is.na(r)); h <- h[order(r[h], dist[h], method = "radix")]; dist[h[1]] })
  out[df$category != "Single Malt Scotch" | grepl(OTHER_BRANDS, low)] <- NA
  unname(out)
}

text_alignment <- function(df, head = 150) {
  brand_of <- function(x) {                                # "distilled at X" else the first word (first "the " dropped)
    m <- regmatches(x, regexpr("distilled at [a-z']+", x))
    if (length(m)) return(sub("distilled at ", "", m))
    y <- sub("the ", "", x, fixed = TRUE)
    w <- regmatches(y, regexpr("[a-z']+", y))
    if (length(w)) w else ""
  }
  brand <- vapply(tolower(df$name), brand_of, "", USE.NAMES = FALSE)
  text <- tolower(df$description); n <- nrow(df)
  share <- function(rows, shift) {
    j <- rows + shift; ok <- j >= 1 & j <= n
    rows <- rows[ok]; j <- j[ok]
    ok <- nchar(brand[j]) >= 4 & text[rows] != ""
    round(mean(mapply(grepl, brand[j][ok], text[rows][ok], MoreArgs = list(fixed = TRUE))), 4)
  }
  top <- seq_len(head); rest <- (head + 1):n
  list(rows_top = head, same_row_top = share(top, 0), same_row_rest = share(rest, 0),
       shifted_rest = round(mean(sapply(c(-3, -2, -1, 1, 2, 3), function(s) share(rest, s))), 4))
}
