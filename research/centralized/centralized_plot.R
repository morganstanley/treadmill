library(plotly)

dt <- read.table("../centralized_response_times.data")
colnames(dt) = c("posibility", "response")

label_1 <- list(
  xref = 'x',
  yref = 'y',
  x = dt$response[66],
  y = dt$posibility[66],
  xanchor = 'right',
  yanchor = 'bottom',
  text = ~paste(dt$posibility[66] * 100, "%, 100.5"),
  font = list(
              size = 16,
              color = 'rgba(67,67,67,1)'),
  showarrow = FALSE)

plotly::plot_ly(x = dt$response, y = dt$posibility, type = 'scatter', mode = 'lines', line = list(color = 'rgba(67,67,67,1)', width = 2), showlegend = FALSE, autosize = FALSE) %>%
  add_trace(x = c(dt$response[66]), y = c(dt$posibility[66]), type = 'scatter', mode = 'markers', marker = list(color = 'rgba(67,67,67,1)', size = 10)) %>%
  layout(title = "CDF") %>%
  layout(annotations = label_1)