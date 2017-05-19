library(plotly)

dt <- read.table("500-node-from-500-to-1000-app.txt", 
                 sep="\t",
                 col.names=c("number", "time", "time10"),
                 fill=FALSE,
                 strip.white=TRUE)

#fit1 <- lm( dt$time~poly(dt$number,1))
#xx <- seq(500, 999, 10)
#fitting <- data.frame(xx, predict(fit1, data.frame(x=xx)))

p1 <- plotly::plot_ly(x = dt$number, y = dt$time, color = dt$time) %>%
  add_lines(name = ~"1")
# p2 <- plotly::plot_ly(x = dt$number, y = dt$time10, color = dt$time10) %>%
#   add_lines(name = ~"10")
subplot(p1)

# x <- dt$number
# y <- dt$time
# plot(dt$number,dt$time)
# lo <- loess(y~x)
# lines(x, predict(lo), col='red', lwd=2)
