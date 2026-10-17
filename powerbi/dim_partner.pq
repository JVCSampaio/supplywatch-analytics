let
    Raw = Csv.Document(File.Contents(DataFolder & "/dim_partner.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Raw, [PromoteAllScalars=true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Nulls, {{"partner_id", type text}, {"partner_name", type text}, {"region", type text}, {"segment", type text}}, "en-US")
in
    Typed
