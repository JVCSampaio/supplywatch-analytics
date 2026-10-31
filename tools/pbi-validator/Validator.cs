using Microsoft.AnalysisServices.Tabular;

// TOM metadata validation only. Does not execute DAX/M or render Desktop visuals.
foreach (string root in args)
{
    string fullRoot = Path.GetFullPath(root);
    string directory = Path.Combine(fullRoot, "reports", "runtime", "tmdl-check");
    Directory.CreateDirectory(directory);
    var lines = File.ReadAllLines(Path.Combine(fullRoot, "powerbi", "model.tmdl"));
    var model = lines.SkipWhile(l => !l.TrimStart().StartsWith("model Model"))
        .Select(l => l.StartsWith("\t") ? l[1..] : l);
    File.WriteAllText(Path.Combine(directory, "database.tmdl"), "database Portfolio\n\tcompatibilityLevel: 1600\n");
    File.WriteAllLines(Path.Combine(directory, "model.tmdl"), model);
    var db = TmdlSerializer.DeserializeDatabaseFromFolder(directory);
    if (db.Model.Tables.Count != 4 || db.Model.Relationships.Count != 3)
        throw new Exception("Expected four tables and three relationships.");
    foreach (var relationship in db.Model.Relationships.Cast<SingleColumnRelationship>())
        if (relationship.FromColumn == null || relationship.ToColumn == null)
            throw new Exception("Unresolved relationship.");
    var measures = db.Model.Tables.Sum(t => t.Measures.Count);
    var result = new {
        parser = "Microsoft.AnalysisServices 19.118.3",
        tmdl_parse = "passed", tables = db.Model.Tables.Count,
        relationships = db.Model.Relationships.Count, measures,
        dax_execution = "not_run", power_query_execution = "not_run",
        desktop_visual_validation = "not_run"
    };
    var json = System.Text.Json.JsonSerializer.Serialize(result, new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
    File.WriteAllText(Path.Combine(fullRoot, "reports", "sample", "powerbi_validation.json"), json);
    Console.WriteLine(root + ": " + json);

    string pbipFolder = Path.Combine(fullRoot, "SupplyWatch.SemanticModel", "definition");
    var pbip = TmdlSerializer.DeserializeDatabaseFromFolder(pbipFolder);
    if (pbip.Model.Tables.Count != 6 || pbip.Model.Relationships.Count != 7)
        throw new Exception($"PBIP model expected 6 tables and 7 relationships, found {pbip.Model.Tables.Count} and {pbip.Model.Relationships.Count}.");
    foreach (var relationship in pbip.Model.Relationships.Cast<SingleColumnRelationship>())
    {
        if (relationship.FromColumn == null || relationship.ToColumn == null)
            throw new Exception("Unresolved PBIP relationship " + relationship.Name);
    }
    var dateTable = pbip.Model.Tables.Find("dim_date");
    if (dateTable == null || dateTable.DataCategory != "Time")
        throw new Exception("dim_date is not marked as a date table.");
    if (pbip.Model.Expressions.Find("DataFolder") == null)
        throw new Exception("DataFolder parameter is missing.");
    int pbipMeasures = pbip.Model.Tables.Sum(t => t.Measures.Count);
    if (pbipMeasures < 20)
        throw new Exception("PBIP measure count is too small: " + pbipMeasures);
    var pbipResult = new {
        parser = "Microsoft.AnalysisServices 19.118.3",
        tmdl_parse = "passed",
        tables = pbip.Model.Tables.Count,
        relationships = pbip.Model.Relationships.Count,
        measures = pbipMeasures,
        date_table = dateTable.Name,
        data_folder_parameter = "DataFolder",
        dax_execution = "not_run",
        power_query_execution = "not_run",
        desktop_visual_validation = "not_run"
    };
    var pbipJson = System.Text.Json.JsonSerializer.Serialize(pbipResult, new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
    File.WriteAllText(Path.Combine(fullRoot, "reports", "sample", "pbip_tmdl.json"), pbipJson);
    Console.WriteLine(root + " pbip: " + pbipJson);
}
