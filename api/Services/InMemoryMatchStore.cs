using Ttts.Api.Models;

namespace Ttts.Api.Services;

public sealed class InMemoryMatchStore : IMatchStore
{
    private readonly object _gate = new();
    private readonly Dictionary<string, LiveMatch> _matches = DemoMatches.Create().ToDictionary(match => match.Id);

    public Task<IReadOnlyList<LiveMatch>> GetMatchesAsync()
    {
        lock (_gate)
        {
            IReadOnlyList<LiveMatch> matches = _matches.Values
                .OrderBy(match => match.Table)
                .Select(MatchScoreRules.Copy)
                .ToList();
            return Task.FromResult(matches);
        }
    }

    public Task<ScoreChangeResult> ChangePointsAsync(string matchId, ScoreChangeRequest request)
    {
        lock (_gate)
        {
            if (!_matches.TryGetValue(matchId, out var match))
            {
                return Task.FromResult(new ScoreChangeResult(null, ScoreChangeFailure.NotFound));
            }

            var result = MatchScoreRules.Apply(match, request);
            return Task.FromResult(result.Match is null
                ? result
                : result with { Match = MatchScoreRules.Copy(result.Match) });
        }
    }
}