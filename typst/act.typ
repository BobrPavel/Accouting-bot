#import "../ru-numbers.typ": ru-words, ru-month
#import "@preview/zero:0.3.3": num, set-group
#set-group(size: 3, separator: sym.space.thin, threshold: 4)

#show heading: set text(font: "Arial", size: 14pt)
#set text(font: "Arial", size: 9pt)
#set par(leading: 5pt)


#set page(margin: (
    top: 1cm,
    left: 2cm,
    right: 1cm,
))

#let act = json("act.json")

#let act_sum = act.jobs.map(job => job.at("price")).sum()



#let day = datetime.today().display("[day]")
#let month = datetime.today().display("[month]")
#let year = datetime.today().display("[year]")



= Акт № #act.at("number")  от #day #ru-month(month) #year
#line(length: 100%)



#table(
  columns: 2,
  stroke: none,
  inset: (left: 0pt),
  [  Исполнитель:], [*#act.executor.at("name"), ИНН #act.executor.at("INN"), р/c #act.executor.at("bank").at("current_account"), в банке #act.executor.at("bank").at("name"), БИК #act.executor.at("bank").at("BIC"), к/с #act.executor.at("bank").at("corporate_account")*],
  [  Заказчик:], [*#act.customer.at("name"), ИНН #act.customer.at("INN"), КПП #act.customer.at("KPP"), #act.customer.at("address")*],
  [  Основание:], [#act.at("base")]
)





#table(
  columns: (1fr, 8fr, 2fr, 1.5fr, 2.5fr, 2.5fr),


  table.header(align(center)[*№*], align(center)[*Наименование товара*], align(center)[*Кол-во*], align(center)[*Ед.*], align(center)[*Цена*], align(center)[*Сумма*]),
  align: (right, left, right, center, right, right),


  ..for (index, job) in act.jobs.enumerate() {(
    

    [
      
      #text(size: 7pt, font: "Arial")[#(index + 1)]
    ],[
      #text(size: 7pt, font: "Arial")[#job.at("task")]
    ], [
      #text(size: 7pt, font: "Arial")[1]
    ], [
      #text(size: 7pt, font: "Arial")[шт]
    ], [
      #text(size: 7pt, font: "Arial")[#num(job.at("price"))]
    ], [
      #text(size: 7pt, font: "Arial")[#num(job.at("price"))]
    ]
    
  )},
)



#align(right, block[
    #table(
      align: right,
      columns: 2,
      stroke: none,
      inset: (right: 9pt),
      [*Итого:*], [*#num(act_sum),00*],
      [*Без налога НДС:*], [*-*],
    )
])

Всего оказано услуг #act.at("count"), на сумму #num(act_sum) руб. \ *#ru-words(act_sum) рублей 00 копеек*


Вышеперечисленные услуги выполнены полностью и в срок. Заказчик претензий по объему, качеству и срокам
оказания услуг не имеет.
#line(length: 100%)


#table(
  
  columns: 3,
  stroke: none,
  inset: (0pt),
  [*ИСПОЛНИТЕЛЬ*\ #act.executor.at("name")\ #line(length: 90%)], [], [*ЗАКАЗЧИК*\ #act.customer.at("name")\ #line(length: 100%)],
)
