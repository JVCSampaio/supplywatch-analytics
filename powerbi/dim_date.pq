let
    Raw = Csv.Document(File.Contents(DataFolder & "/dim_date.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Raw, [PromoteAllScalars=true]),
    Nulls = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Nulls, {{"date", type date}, {"year", Int64.Type}, {"month", type text}}, "en-US")
in
    Typed
