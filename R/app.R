# Shiny version of the atlas.   shiny::runApp("R")
# Reads web/data/whisky.json (built by python/build_web.py) — same data as the static site.
if (!isTRUE(l10n_info()[["UTF-8"]])) invisible(Sys.setlocale("LC_CTYPE", "C.UTF-8"))  # Turkish labels
library(shiny)
library(bslib)
library(jsonlite)
library(httr2)

root <- if (file.exists("web/data/whisky.json")) "." else ".."
D <- fromJSON(file.path(root, "web", "data", "whisky.json"), simplifyVector = FALSE)
d <- D$d
nm <- unlist(d$n)
Fm <- do.call(rbind, lapply(d$f, unlist))
ST <- unlist(d$st) + 1
FLAV <- list(tr = c("Gövde", "Tatlılık", "Duman", "İyot / tıbbi", "Tütün", "Bal", "Baharat", "Şarapsı / şeri", "Kuruyemiş", "Malt", "Meyve", "Çiçek"),
             en = c("Body", "Sweetness", "Smoky", "Medicinal", "Tobacco", "Honey", "Spicy", "Winey / sherry", "Nutty", "Malty", "Fruity", "Floral"))
STYLE <- list(tr = c("dumanlı / iyotlu", "şeri / şarapsı", "hafif", "ballı / dengeli"),
              en = c("smoky / medicinal", "sherried / winey", "light", "honeyed / balanced"))
MAXD <- 4 * sqrt(12)
match_pct <- function(dist) sprintf("%d%%", round(100 * (1 - dist / MAXD)))
shelf_of <- function(i) lapply(unlist(d$tr[[i]]) + 1, function(k) D$shelf[[k]])
prov <- do.call(rbind, lapply(D$provinces, function(p) data.frame(name = p[[1]], lat = p[[2]], lon = p[[3]])))
# the static map's SVG path ("Mx,yLx,y...Z") → polygons for base graphics
rings <- lapply(strsplit(D$map$path, "Z ?")[[1]], function(r) {
  xy <- matrix(as.numeric(unlist(strsplit(gsub("[ML]", " ", r), "[ ,]+"))[-1]), ncol = 2, byrow = TRUE); xy })

haversine <- function(a, b) {
  r <- pi / 180
  h <- sin((b[1] - a[1]) * r / 2)^2 + cos(a[1] * r) * cos(b[1] * r) * sin((b[2] - a[2]) * r / 2)^2
  12742 * asin(sqrt(h))
}
shops <- function(lat, lon) {
  for (radius in c(3000, 10000, 30000)) {
    q <- sprintf('[out:json][timeout:20];(nwr["shop"~"^(alcohol|wine|beverages)$"](around:%d,%f,%f););out center 80;', radius, lat, lon)
    js <- request("https://overpass-api.de/api/interpreter") |> req_body_form(data = q) |> req_timeout(30) |> req_perform() |> resp_body_json()
    out <- do.call(rbind, lapply(js$elements, function(e) {
      la <- if (!is.null(e$lat)) e$lat else e$center$lat
      lo <- if (!is.null(e$lon)) e$lon else e$center$lon
      data.frame(km = round(haversine(c(lat, lon), c(la, lo)), 1), name = if (is.null(e$tags$name)) "—" else e$tags$name,
                 type = if (is.null(e$tags$shop)) "" else e$tags$shop, osm = sprintf("https://www.openstreetmap.org/%s/%s", e$type, e$id))
    }))
    if ((!is.null(out) && nrow(out) >= 5) || radius == 30000) return(if (is.null(out)) out else head(out[order(out$km), ], 12))
  }
}

ui <- page_navbar(
  title = "Scotch Whisky Flavour Atlas",
  theme = bs_theme(version = 5, bg = "#f5f2ec", fg = "#1a1612", primary = "#93520f", base_font = "IBM Plex Sans, system-ui"),
  sidebar = sidebar(radioButtons("lang", NULL, setNames(c("tr", "en"), c("Türkçe", "English")), inline = TRUE),
                    selectInput("dist", "Damıtımevi / Distillery", choices = setNames(seq_along(nm), nm), selected = match("Lagavulin", nm)),
                    plotOutput("map", height = "420px", click = "map_click")),
  nav_panel("Damıtımevi / Distillery", uiOutput("card")),
  nav_panel("Tat / Taste",
            do.call(layout_columns, c(list(col_widths = 3), lapply(1:12, function(k) sliderInput(paste0("f", k), FLAV$en[k], 0, 4, round(mean(Fm[, k])), step = 1)))),
            uiOutput("taste_out")),
  nav_panel("Nereden? / Where?",
            selectInput("prov", "İl / Province", choices = setNames(seq_len(nrow(prov)), prov$name), selected = 34),
            actionButton("go", "Ara / Search", class = "btn-primary"),
            tableOutput("shops"),
            p(class = "text-muted", "22.00–06.00 arası perakende satış ve 18 yaş altına satış yasaktır (4250 s. Kanun md. 6). © OpenStreetMap contributors (ODbL)"))
)

server <- function(input, output, session) {
  L <- reactive(input$lang)
  i <- reactive(as.integer(input$dist))
  observeEvent(input$map_click, {
    xy <- c(input$map_click$x, -input$map_click$y)
    j <- which.min((unlist(d$x) - xy[1])^2 + (unlist(d$y) - xy[2])^2)
    updateSelectInput(session, "dist", selected = j)
  })
  output$map <- renderPlot({
    par(mar = c(0, 0, 0, 0), bg = "#f5f2ec")
    plot(NA, xlim = c(0, D$map$w), ylim = c(-D$map$h, 0), asp = 1, axes = FALSE, xlab = "", ylab = "")
    for (r in rings) polygon(r[, 1], -r[, 2], col = "#ece4d6", border = "#cbbba3")
    peat <- Fm[, 3] + Fm[, 4]
    points(unlist(d$x), -unlist(d$y), pch = 21, cex = 1 + peat / 5, bg = colorRampPalette(c("#fff8ea", "#93520f"))(9)[peat + 1], col = "#453d35")
    points(d$x[[i()]], -d$y[[i()]], pch = 21, cex = 2.8, lwd = 3, col = "#1a1612")
  })
  output$card <- renderUI({
    i <- i(); tr <- L() == "tr"; T <- function(a, b) if (tr) a else b
    rule <- Filter(function(r) r$rule_id == D$styles[[ST[i]]], D$rules)[[1]]
    ch <- Filter(function(c) c$id %in% strsplit(rule$cheese_ids, ";")[[1]], D$cheeses)
    wa <- d$wa[[i]]
    tagList(
      h3(nm[i]),
      layout_columns(value_box(T("Tarz", "Style"), STYLE[[L()]][ST[i]]), value_box(T("Bölge", "Area"), if (d$isl[[i]] == 1) "Islay" else d$pc[[i]]),
                     value_box("Whisky Advocate", if (is.null(wa)) "—" else sprintf("%.1f", wa[[2]]), if (!is.null(wa)) T(paste(wa[[1]], "inceleme"), paste(wa[[1]], "reviews")))),
      renderPlot({ par(mar = c(3, 9, 1, 1)); barplot(rev(Fm[i, ]), names.arg = rev(FLAV[[L()]]), horiz = TRUE, las = 1, xlim = c(0, 4), col = "#93520f", border = NA) }, height = 300),
      if (length(d$tr[[i]])) tagList(h5(T("Türkiye'de satılan şişeleri", "Its bottles sold in Türkiye")),
        tags$ul(lapply(shelf_of(i), function(p) tags$li(sprintf("%s — %s TL (%s)", p$product, if (p$price_tl == "") "—" else p$price_tl, p$as_of))))),
      h5(T("Türkiye'de bulabileceğin en yakın tatlar", "Closest tastes you can buy in Türkiye")),
      tags$ul(lapply(d$alt[[i]], function(a) { j <- a[[1]] + 1
        tags$li(sprintf("%s (%s) — %s", nm[j], match_pct(a[[2]]), paste(vapply(shelf_of(j), function(p) p$product, ""), collapse = ", "))) })),
      h5(T("Tadı en çok benzeyenler", "Most similar in taste")),
      tags$ul(lapply(d$nb[[i]], function(a) tags$li(sprintf("%s (%s)", nm[a[[1]] + 1], match_pct(a[[2]]))))),
      h5(T("Yanına peynir", "Cheese to pair")), p(if (tr) rule$rationale_tr else rule$rationale_en),
      p(paste(vapply(ch, function(c) if (tr) c$name_tr else c$name_en, ""), collapse = ", "))
    )
  })
  output$taste_out <- renderUI({
    want <- vapply(1:12, function(k) as.numeric(input[[paste0("f", k)]]), 0)
    dist <- sqrt(rowSums(sweep(Fm, 2, want)^2))
    o <- order(dist, method = "radix")
    on_shelf <- head(o[vapply(o, function(j) length(d$tr[[j]]) > 0, TRUE)], 4)
    tagList(h5(if (L() == "tr") "Türkiye'de bulabileceklerin" else "What you can buy in Türkiye"),
            tags$ol(lapply(on_shelf, function(j) tags$li(sprintf("%s (%s)", nm[j], match_pct(dist[j]))))),
            h5(if (L() == "tr") "Bu tada en yakın damıtımevleri" else "Distilleries closest to this taste"),
            tags$ol(lapply(head(o, 8), function(j) tags$li(sprintf("%s (%s)", nm[j], match_pct(dist[j]))))))
  })
  output$shops <- renderTable({
    input$go; isolate({ p <- prov[as.integer(input$prov), ]; req(input$go > 0); shops(p$lat, p$lon) })
  })
}

shinyApp(ui, server)
