library(plotly)

dt <- read.table("500-app-from-500-to-1000-node.txt",
                 col.names=c("number", "time"),
                 fill=FALSE,
                 strip.white=TRUE)

l1 = lm(data = dt, time ~ number)
l2 = lm(data = dt, time ~ I(number^2))

p <- plot_ly(data = dt, x = ~number, y = ~time, name = 'raw data', type = 'scatter') %>% 
  add_trace(y = predict(l1), mode = 'lines', name = 'linear')

p
