using Ttts.Api.Models;

namespace Ttts.Api.Services;

public interface IMatchStore
{
    Task<IReadOnlyList<LiveMatch>> GetMatchesAsync();
    Task<ScoreChangeResult> ChangePointsAsync(string matchId, ScoreChangeRequest request);
}

internal static class MatchScoreRules
{
    public static ScoreChangeResult Apply(LiveMatch match, ScoreChangeRequest request)
    {
        if (match.Status != "live")
        {
            return new(null, ScoreChangeFailure.MatchNotLive);
        }

        if (match.Version != request.ExpectedVersion)
        {
            return new(null, ScoreChangeFailure.Conflict);
        }

        var nextPoints = match.Players[request.PlayerIndex].Points + request.Delta;
        if (nextPoints < 0)
        {
            return new(null, ScoreChangeFailure.NegativeScore);
        }

        match.Players[request.PlayerIndex].Points = nextPoints;
        match.Version++;
        return new(match, ScoreChangeFailure.None);
    }

    public static LiveMatch Copy(LiveMatch match) => new()
    {
        Id = match.Id,
        Group = match.Group,
        Table = match.Table,
        CurrentSet = match.CurrentSet,
        Status = match.Status,
        Version = match.Version,
        Players = match.Players.Select(player => new LivePlayerScore
        {
            Name = player.Name,
            Sets = player.Sets,
            Points = player.Points,
        }).ToList(),
    };
}