#import "ru-numbers.typ": ru-words
#import "@preview/zero:0.3.3": num, set-group
#set-group(size: 3, separator: sym.space.thin, threshold: 4)

#let act = json("act.json")

#let act_sum = act.jobs.map(job => job.at("price")).sum()

= Акт выполненных работ

#datetime.today().display("[day].[month].[year]")

#table(
  columns: 2,
  stroke: none,
  inset: (left: 0pt),
  [*Исполнитель:*], [#act.executor.at("name")],
  [*Заказчик:*],    [#act.customer.at("name")],
)

#table(
  columns: 6,
  [№], [Наименование товара], [Ед. изм.], [Кол-во], [Цена, ₽], [Сумма, ₽],
  ..for (index, job) in act.jobs.enumerate() {(
    [
      #align(center)[#(index + 1)]
    ],[
      #job.at("task")
    ], [
      #align(center)[шт]
    ], [
      #align(center)[1]
    ], [
      #align(center)[#num(job.at("price"))]
    ], [
      #align(center)[#num(job.at("price"))]
    ]
  )},
)

Общая стоимость выполненных работ, оказанных услуг в российских рублях: 
#num(act_sum) (#ru-words(act_sum)) 00 копеек. 
Заказчик не имеет претензий по срокам, качеству и объёму товаров и услуг.

#table(
  columns: 2,
  stroke: none,
  inset: (left: 0pt),
  [
    *#act.customer.at("name")*
  ], [
    *#act.executor.at("name")*
  ], 
  text()[

    ИНН: #act.customer.at("INN")\
    ОГРН: #act.customer.at("OGRN")\
    Юридический адрес: #act.customer.at("address")\
    Банк: #act.customer.at("bank").at("name")\
    БИК: #act.customer.at("bank").at("BIC")\
    Расчетный счёт: #act.customer.at("bank").at("current_account")\
    Корр. счёт: #act.customer.at("bank").at("corporate_account")
  ],[
    ИНН: #act.executor.at("INN")\
    ОГРНИП: #act.executor.at("OGRN")\
    Р/с: #act.executor.at("bank").at("current_account")\
    Банк: #act.executor.at("bank").at("name")\
    БИК: #act.executor.at("bank").at("BIC")\
    Корр. счёт: #act.executor.at("bank").at("corporate_account")
  ],[
    \
    #text("________________/") #act.customer.at("signatory") /
  ], [
    \
    #text("________________/") #act.executor.at("signatory") /
  ]
)
