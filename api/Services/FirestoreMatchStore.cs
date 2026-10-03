using Google.Cloud.Firestore;
using Ttts.Api.Models;

namespace Ttts.Api.Services;

public sealed class FirestoreMatchStore(FirestoreDb database) : IMatchStore
{
    private readonly CollectionReference _matches = database.Collection("matches");
    private readonly SemaphoreSlim _seedLock = new(1, 1);
    private bool _seeded;

    public async Task<IReadOnlyList<LiveMatch>> GetMatchesAsync()
    {
        await EnsureSeededAsync();
        var snapshot = await _matches.GetSnapshotAsync();
        return snapshot.Documents
            .Select(document => document.ConvertTo<LiveMatch>())
            .OrderBy(match => match.Table)
            .ToList();
    }

    public async Task<ScoreChangeResult> ChangePointsAsync(string matchId, ScoreChangeRequest request)
    {
        await EnsureSeededAsync();
        var reference = _matches.Document(matchId);

        return await database.RunTransactionAsync(async transaction =>
        {
            var snapshot = await transaction.GetSnapshotAsync(reference);
            if (!snapshot.Exists)
            {
                return new ScoreChangeResult(null, ScoreChangeFailure.NotFound);
            }

            var match = snapshot.ConvertTo<LiveMatch>();
            var result = MatchScoreRules.Apply(match, request);
            if (result.Match is not null)
            {
                transaction.Set(reference, result.Match);
            }

            return result;
        });
    }

    private async Task EnsureSeededAsync()
    {
        if (_seeded)
        {
            return;
        }

        await _seedLock.WaitAsync();
        try
        {
            if (_seeded)
            {
                return;
            }

            var snapshot = await _matches.Limit(1).GetSnapshotAsync();
            if (snapshot.Count == 0)
            {
                var batch = database.StartBatch();
                foreach (var match in DemoMatches.Create())
                {
                    batch.Set(_matches.Document(match.Id), match);
                }

                await batch.CommitAsync();
            }

            _seeded = true;
        }
        finally
        {
            _seedLock.Release();
        }
    }
}