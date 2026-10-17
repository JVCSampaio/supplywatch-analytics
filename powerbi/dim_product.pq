let
    Raw = Csv.Document(File.Contents(DataFolder & "/dim_product.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Raw, [PromoteAllScalars=true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Nulls, {{"product_id", type text}, {"product_name", type text}, {"category", type text}}, "en-US")
in
    Typed
