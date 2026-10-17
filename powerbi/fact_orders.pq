let
    Raw = Csv.Document(File.Contents(DataFolder & "/fact_orders.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Raw, [PromoteAllScalars=true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Nulls, {{"line_id", type text}, {"order_id", type text}, {"order_date", type date}, {"partner_id", type text}, {"product_id", type text}, {"quantity", Int64.Type}, {"unit_price_cents", Int64.Type}, {"status", type text}, {"due_date", type date}, {"received_quantity", Int64.Type}, {"on_time_quantity", Int64.Type}, {"last_received_date", type date}, {"amount_cents", Int64.Type}, {"open_quantity", Int64.Type}, {"open_cents", Int64.Type}, {"due_eligible", Int64.Type}, {"otif", Int64.Type}, {"lead_days", type number}, {"overdue_cents", Int64.Type}}, "en-US")
in
    Typed
