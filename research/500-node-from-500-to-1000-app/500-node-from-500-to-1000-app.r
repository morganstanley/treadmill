library(plotly)

dt <- read.table("500-node-from-500-to-1000-app-linear.txt",
                 col.names=c("number", "time"),
                 fill=FALSE,
                 strip.white=TRUE)

l1 = lm(data = dt, time ~ number)
l2 = lm(data = dt, time ~ I(number^2))

p <- plot_ly(data = dt, x = ~number, y = ~time, name = 'raw data', type = 'scatter') %>% 
  add_trace(y = predict(l1), mode = 'lines', name = 'linear') %>%
  add_trace(y = predict(l2), mode = 'lines', name = 'X^2')

p
