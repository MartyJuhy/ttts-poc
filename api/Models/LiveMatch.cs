using Google.Cloud.Firestore;

namespace Ttts.Api.Models;

[FirestoreData]
public sealed class LiveMatch
{
    [FirestoreDocumentId]
    public string Id { get; set; } = string.Empty;

    [FirestoreProperty]
    public string Group { get; set; } = string.Empty;

    [FirestoreProperty]
    public int Table { get; set; }

    [FirestoreProperty]
    public int CurrentSet { get; set; }

    [FirestoreProperty]
    public string Status { get; set; } = "live";

    [FirestoreProperty]
    public int Version { get; set; }

    [FirestoreProperty]
    public List<LivePlayerScore> Players { get; set; } = [];
}

[FirestoreData]
public sealed class LivePlayerScore
{
    [FirestoreProperty]
    public string Name { get; set; } = string.Empty;

    [FirestoreProperty]
    public int Sets { get; set; }

    [FirestoreProperty]
    public int Points { get; set; }
}

public sealed record ScoreChangeRequest(int PlayerIndex, int Delta, int ExpectedVersion);

public enum ScoreChangeFailure
{
    None,
    NotFound,
    Conflict,
    NegativeScore,
    MatchNotLive,
}

public sealed record ScoreChangeResult(LiveMatch? Match, ScoreChangeFailure Failure);

public static class DemoMatches
{
    public static List<LiveMatch> Create() =>
    [
        new()
        {
            Id = "match-1", Group = "A", Table = 1, CurrentSet = 4, Status = "live", Version = 0,
            Players = [new() { Name = "Ladislav Novák", Sets = 2, Points = 8 }, new() { Name = "Petr Svoboda", Sets = 1, Points = 6 }],
        },
        new()
        {
            Id = "match-2", Group = "A", Table = 2, CurrentSet = 3, Status = "live", Version = 0,
            Players = [new() { Name = "Jiří Dvořák", Sets = 1, Points = 10 }, new() { Name = "Milan Král", Sets = 1, Points = 9 }],
        },
        new()
        {
            Id = "match-3", Group = "B", Table = 3, CurrentSet = 1, Status = "live", Version = 0,
            Players = [new() { Name = "Karel Černý", Sets = 0, Points = 5 }, new() { Name = "Pavel Marek", Sets = 0, Points = 7 }],
        },
    ];
}