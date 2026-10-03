using Ttts.Api.Models;
using Ttts.Api.Services;

namespace api.Tests;

public class InMemoryMatchStoreTests
{
    [Fact]
    public async Task ChangePointsAsync_updates_selected_player_and_version()
    {
        var store = new InMemoryMatchStore();
        var result = await store.ChangePointsAsync("match-1", new ScoreChangeRequest(0, 1, 0));

        Assert.Equal(ScoreChangeFailure.None, result.Failure);
        Assert.Equal(9, result.Match!.Players[0].Points);
        Assert.Equal(1, result.Match.Version);
    }

    [Fact]
    public async Task ChangePointsAsync_rejects_negative_score()
    {
        var store = new InMemoryMatchStore();
        var result = await store.ChangePointsAsync("match-3", new ScoreChangeRequest(1, -8, 0));

        Assert.Equal(ScoreChangeFailure.NegativeScore, result.Failure);
        var matches = await store.GetMatchesAsync();
        Assert.Equal(7, matches.Single(match => match.Id == "match-3").Players[1].Points);
    }

    [Fact]
    public async Task ChangePointsAsync_rejects_stale_version()
    {
        var store = new InMemoryMatchStore();
        await store.ChangePointsAsync("match-1", new ScoreChangeRequest(0, 1, 0));
        var staleUpdate = await store.ChangePointsAsync("match-1", new ScoreChangeRequest(1, 1, 0));

        Assert.Equal(ScoreChangeFailure.Conflict, staleUpdate.Failure);
    }
}
